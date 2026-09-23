var Packet = require('./packet');
var BinaryWriter = require("./packet/BinaryWriter");

function PlayerTracker(gameServer, socket) {
    this.gameServer = gameServer;
    this.socket = socket;
    this.pID = -1;
    this.userAuth = null;
    this.isRemoved = false;
    this.isCloseRequested = false;
    this._name = "";
    this._skin = "";
    this._nameUtf8 = null;
    this._nameUnicode = null;
    this._skinUtf8 = null;
    this.color = { r: 0, g: 0, b: 0 };
    this.viewNodes = [];
    this.clientNodes = [];
    this.cells = [];
    this.mergeOverride = false; // Triggered by console command
    this._score = 0; // Needed for leaderboard
    this._scale = 1;
    this.isMassChanged = true;
    this.borderCounter = 0;
    this.connectedTime = new Date();

    this.team = 0;
    this.spectate = false;
    this.freeRoam = false;      // Free-roam mode enables player to move in spectate mode
    this.lastKeypressTick = 0;

    this.centerPos = {
        x: 0,
        y: 0
    };
    this.mouse = {
        x: 0,
        y: 0
    };
    this.viewBox = {
        minx: 0,
        miny: 0,
        maxx: 0,
        maxy: 0,
        halfWidth: 0,
        halfHeight: 0
    };

    // Scramble the coordinate system for anti-raga
    this.scrambleX = 0;
    this.scrambleY = 0;
    this.scrambleId = 0;
    this.isMinion = false;
    this.isMuted = false;

    // Custom commands
    this.spawnmass = 0;
    this.frozen = false;
    this.customspeed = 0;
    this.rec = false;

    // Minions
    this.miQ = 0;
    this.isMi = false;
    this.minionSplit = false;
    this.minionEject = false;
    this.minionFrozen = false;
    this.minionControl = false;
    this.collectPellets = false;

    // Gamemode function
    if (gameServer) {
        this.centerPos.x = 0;
        this.centerPos.y = 0;
        // Player id
        this.pID = gameServer.lastPlayerId++ >> 0;
        // Gamemode function
        gameServer.gameMode.onPlayerInit(this);
        // Only scramble if enabled in config
        this.scramble();
    }
    var UserRoleEnum = require("./enum/UserRoleEnum");
    this.userRole = UserRoleEnum.GUEST;
}

module.exports = PlayerTracker;

// Setters/Getters

PlayerTracker.prototype.scramble = function() {
    if (!this.gameServer.config.serverScrambleLevel) {
        this.scrambleId = 0;
        this.scrambleX = 0;
        this.scrambleY = 0;
    } else {
        this.scrambleId = (Math.random() * 0xFFFFFFFF) >>> 0;
        // avoid mouse packet limitations
        var maxx = Math.max(0, 31767 - this.gameServer.border.width);
        var maxy = Math.max(0, 31767 - this.gameServer.border.height);
        var x = maxx * Math.random();
        var y = maxy * Math.random();
        if (Math.random() >= 0.5) x = -x;
        if (Math.random() >= 0.5) y = -y;
        this.scrambleX = x;
        this.scrambleY = y;
    }
    this.borderCounter = 0;
};

PlayerTracker.prototype.setName = function(name) {
    this._name = name;
    if (!name || !name.length) {
        this._nameUnicode = null;
        this._nameUtf8 = null;
        return;
    }
    var writer = new BinaryWriter();
    writer.writeStringZeroUnicode(name);
    this._nameUnicode = writer.toBuffer();
    writer = new BinaryWriter();
    writer.writeStringZeroUtf8(name);
    this._nameUtf8 = writer.toBuffer();
};

PlayerTracker.prototype.setSkin = function(skin) {
    this._skin = skin;
    if (!skin || !skin.length) {
        this._skinUtf8 = null;
        return;
    }
    var writer = new BinaryWriter();
    writer.writeStringZeroUtf8(skin);
    this._skinUtf8 = writer.toBuffer();
};

PlayerTracker.prototype.setColor = function(color) {
    this.color.r = color.r;
    this.color.g = color.g;
    this.color.b = color.b;
};

PlayerTracker.prototype.getScale = function() {
    if (this.isMassChanged) this.updateMass();
    return this._scale;
};

PlayerTracker.prototype.updateMass = function() {
    this._score = 0; // reset to not cause bugs with playerlist
    for (var i = 0; i < this.cells.length; i++) {
        if (!this.cells[i]) continue;
        this._scale += this.cells[i]._size;
        this._score += this.cells[i]._mass;
    }
    if (this._scale) this._scale = Math.pow(Math.min(64 / this._scale, 1), 0.4);
    this.isMassChanged = false;
};

PlayerTracker.prototype.joinGame = function(name, skin) {
    if (this.cells.length) return;

    if (skin) this.setSkin(skin);
    if (!name && this.socket.packetHandler.prototcol >= 11) name = "An unnamed cell";
    else if (!name) name = "";
    this.setName(name);
    this.spectate = false;
    this.freeRoam = false;

    // some old clients don't understand ClearAll message
    // so we will send update for them
    if (this.socket.packetHandler.protocol < 6)
        this.socket.sendPacket(new Packet.UpdateNodes(this, [], [], [], this.clientNodes));

    this.socket.sendPacket(new Packet.ClearAll());
    this.clientNodes = [];
    this.scramble();
    if (this.gameServer.config.serverScrambleLevel < 2) {
        // no scramble / lightweight scramble
        this.socket.sendPacket(new Packet.SetBorder(this, this.gameServer.border));
    }
    else if (this.gameServer.config.serverScrambleLevel == 3) {
        var ran = 10065536 * Math.random();
        // Ruins most known minimaps (no border)
        var border = {
            minx: this.gameServer.border.minx - ran,
            miny: this.gameServer.border.miny - ran,
            maxx: this.gameServer.border.maxx + ran,
            maxy: this.gameServer.border.maxy + ran
        };
        this.socket.sendPacket(new Packet.SetBorder(this, border));
    }
    this.gameServer.gameMode.onPlayerSpawn(this.gameServer, this);
    this.updateMass();
};

PlayerTracker.prototype.checkConnection = function() {
    // Handle disconnection
    if (!this.socket.isConnected) {
        // wait for playerDisconnectTime
        var dt = (this.gameServer.stepDateTime - this.socket.closeTime) / 1000;
        if (!this.cells.length || dt >= this.gameServer.config.playerDisconnectTime) {
            // Remove all client cells
            this.cells = [];
            for (var i = 0; i < this.cells.length; i++)
                this.gameServer.removeNode(this.cells[i]);
            // Mark to remove
            this.isRemoved = true;
            return;
        }
        this.mouse.x = this.centerPos.x;
        this.mouse.y = this.centerPos.y;
        this.socket.packetHandler.pressSpace = false;
        this.socket.packetHandler.pressQ = false;
        this.socket.packetHandler.pressW = false;
        this.minionControl = false;
        return;
    }

    // Check timeout
    if (!this.isCloseRequested && this.gameServer.config.serverTimeout) {
        dt = (this.gameServer.stepDateTime - this.socket.lastAliveTime) / 1000;
        if (dt >= this.gameServer.config.serverTimeout) {
            this.socket.close(1000, "Connection timeout");
            this.isCloseRequested = true;
        }
    }
};

PlayerTracker.prototype.getViewState = function() {
    if (!this.spectate) {
        // in game
        return 0;
    } else {
        if (this.freeRoam || this.getSpectateTarget() == null) {
            // free roam
            return 1;
        } else {
            // spectate target
            return 2;
        }
    }
};

PlayerTracker.prototype.updateTick = function() {
    if (this.isRemoved || this.isMinion)
        return; // do not update
    this.socket.packetHandler.process();

    // update spectators
    if (this.isMi) return;

    // update center
    switch (this.getViewState()) {
        case 0:
            this.updateCenterInGame();
            break;
        case 1:
            this.updateCenterFreeRoam();
            this._scale = this.gameServer.config.serverSpectatorScale;
            break;
        default:
            return;
    }

    // update viewbox
    var scale = Math.max(this.getScale(), this.gameServer.config.serverMinScale);
    var halfWidth = (this.gameServer.config.serverViewBaseX / scale) / 2;
    var halfHeight = (this.gameServer.config.serverViewBaseY / scale) / 2;
    this.viewBox = {
        minx: this.centerPos.x - halfWidth,
        miny: this.centerPos.y - halfHeight,
        maxx: this.centerPos.x + halfWidth,
        maxy: this.centerPos.y + halfHeight,
        halfWidth: halfWidth,
        halfHeight: halfHeight
    };

    // update visible nodes
    this.viewNodes = [];
    var self = this;
    this.gameServer.finder.find(this.viewBox, function(quadItem) {
        if (quadItem.cell.owner != self)
            self.viewNodes.push(quadItem.cell);
    });
    this.viewNodes = this.viewNodes.concat(this.cells);
    this.viewNodes.sort(function(a, b) { return a.nodeId - b.nodeId; });
};

PlayerTracker.prototype.sendUpdate = function() {
    if (this.isRemoved || !this.socket.packetHandler.protocol ||
        !this.socket.isConnected || this.isMi || this.isMinion ||
        (this.socket._socket.writable != null && !this.socket._socket.writable) ||
        this.socket.readyState != this.socket.OPEN) {
        // do not send update for disconnected clients
        // also do not send if initialization is not complete yet
        return;
    }

    var v = this.getViewState();
    if (v !== 0) {
        if (v === 2) {
            // spectate target
            var player = this.getSpectateTarget();
            if (player) {
                this.setCenterPos(player.centerPos.x, player.centerPos.y);
                this._scale = player.getScale();
                this.viewBox = player.viewBox;
                this.viewNodes = player.viewNodes;
            }
        }

        // send camera packet
        this.socket.sendPacket(new Packet.UpdatePosition(
            this, this.centerPos.x, this.centerPos.y, this.getScale()
        ));
    }

    if (this.gameServer.config.serverScrambleLevel == 2) {
        // scramble (moving border)
        if (!this.borderCounter) {
            var b = this.gameServer.border, v = this.viewBox;
            var bound = {
                minx: Math.max(b.minx, v.minx - v.halfWidth),
                miny: Math.max(b.miny, v.miny - v.halfHeight),
                maxx: Math.min(b.maxx, v.maxx + v.halfWidth),
                maxy: Math.min(b.maxy, v.maxy + v.halfHeight)
            };
            this.socket.sendPacket(new Packet.SetBorder(this, bound));
        }
        this.borderCounter++;
        if (this.borderCounter >= 20)
            this.borderCounter = 0;
    }

    var delNodes = [];
    var eatNodes = [];
    var addNodes = [];
    var updNodes = [];
    var oldIndex = 0;
    var newIndex = 0;
    for (; newIndex < this.viewNodes.length && oldIndex < this.clientNodes.length;) {
        if (this.viewNodes[newIndex].nodeId < this.clientNodes[oldIndex].nodeId) {
            addNodes.push(this.viewNodes[newIndex]);
            newIndex++;
            continue;
        }
        if (this.viewNodes[newIndex].nodeId > this.clientNodes[oldIndex].nodeId) {
            var node = this.clientNodes[oldIndex];
            if (node.isRemoved && node.killedBy !== null && node.owner != node.killedBy.owner)
                eatNodes.push(node);
            else
                delNodes.push(node);
            oldIndex++;
            continue;
        }
        var node = this.viewNodes[newIndex];
        // skip food & eject if not moving
        if (node.isMoving || (node.cellType != 1 && node.cellType != 3))
            updNodes.push(node);
        newIndex++;
        oldIndex++;
    }
    for (; newIndex < this.viewNodes.length; ) {
        addNodes.push(this.viewNodes[newIndex]);
        newIndex++;
    }
    for (; oldIndex < this.clientNodes.length; ) {
        var node = this.clientNodes[oldIndex];
        if (node.isRemoved && node.killedBy !== null && node.owner != node.killedBy.owner)
            eatNodes.push(node);
        else
            delNodes.push(node);
        oldIndex++;
    }
    this.clientNodes = this.viewNodes;

    // Send packet
    if (this.socket.isConnected != null) {
        this.socket.sendPacket(new Packet.UpdateNodes(
            this, addNodes, updNodes, eatNodes, delNodes
        ));
        this.sendLeaderboard();
    }
};

PlayerTracker.prototype.sendLeaderboard = function() {
    // Update leaderboard if changed
    if (this.gameServer.leaderboardChanged) {
        var lbType = this.gameServer.leaderboardType,
            lbList = this.gameServer.leaderboard;

        if (lbType >= 0) {
            if (this.socket.packetHandler.protocol >= 11 && this.gameServer.gameMode.specByLeaderboard)
                this.socket.sendPacket(new Packet.LeaderboardPosition(this, lbList.indexOf(this) + 1));
            this.socket.sendPacket(new Packet.UpdateLeaderboard(this, lbList, lbType));
        }
    }
};

PlayerTracker.prototype.updateCenterInGame = function() { // Get center of cells
    if (!this.cells.length) return;
    var cx = 0;
    var cy = 0;
    for (var i = 0; i < this.cells.length; i++) {
        if (!this.cells[i]) continue;
        cx += this.cells[i].position.x;
        cy += this.cells[i].position.y;
    }
    this.centerPos.x = cx / this.cells.length;
    this.centerPos.y = cy / this.cells.length;
};

PlayerTracker.prototype.updateCenterFreeRoam = function() {
    // get distance and speed
    var dx = this.mouse.x - this.centerPos.x;
    var dy = this.mouse.y - this.centerPos.y;
    var d = 32 / Math.sqrt(dx * dx + dy * dy);
    if (!d) return; // stop threshold

    // set center position
    var x = this.centerPos.x + dx * d;
    var y = this.centerPos.y + dy * d;
    this.setCenterPos(x, y);
};

PlayerTracker.prototype.pressSpace = function() {
    if (this.gameServer.run && this.cells.length > 0) {
        // Cant split if merging or frozen
        if (this.mergeOverride || this.frozen)
            return;
        this.gameServer.splitCells(this);
    }
};

PlayerTracker.prototype.pressW = function() {
    if (this.getViewState() !== 0)
        return;
    else if (this.gameServer.run)
        this.gameServer.ejectMass(this);
};

PlayerTracker.prototype.pressQ = function() {
    if (this.getViewState() !== 0) {
        // Check for spam first (to prevent too many add/del updates)
        var tick = this.gameServer.tickCounter;
        if (tick - this.lastKeypressTick < 40)
            return;
        this.lastKeypressTick = tick;

        this.freeRoam = !this.freeRoam;
    }
};

PlayerTracker.prototype.getSpectateTarget = function() {
    return this.gameServer.largestClient;
};

PlayerTracker.prototype.setCenterPos = function(x, y) {
    x = Math.max(x, this.gameServer.border.minx);
    y = Math.max(y, this.gameServer.border.miny);
    x = Math.min(x, this.gameServer.border.maxx);
    y = Math.min(y, this.gameServer.border.maxy);
    this.centerPos.x = x;
    this.centerPos.y = y;
};
