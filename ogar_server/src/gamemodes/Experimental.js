var FFA = require('./FFA'); // Base gamemode
var Entity = require('../entity');
var Logger = require('../modules/Logger');

function Experimental() {
    FFA.apply(this, Array.prototype.slice.call(arguments));

    this.ID = 2;
    this.name = "Experimental";
    this.specByLeaderboard = true;

    // Gamemode-specific variables
    this.nodesMother = [];
    this.tickMotherSpawn = 0;
    this.tickMotherUpdate = 0;

    // Config
    this.motherSpawnInterval = 125;  // How many ticks it takes to spawn another mother cell (5 seconds)
    this.motherMinAmount = 10;
}

module.exports = Experimental;
Experimental.prototype = new FFA();

// Gamemode-specific functions

Experimental.prototype.spawnMotherCell = function(gameServer) {
    // Checks if there are enough mother cells on the map
    if (this.nodesMother.length >= this.motherMinAmount)
        return;

    // Spawns a mother cell
    var pos = gameServer.randomPos();
    if (gameServer.willCollide(pos, 149))
        // cannot find safe position => do not spawn
        return;

    // Spawn if no cells are colliding
    var mother = new Entity.MotherCell(gameServer, null, pos, null);
    gameServer.addNode(mother);
};

// Override
Experimental.prototype.onServerInit = function(gameServer) {
    // Called when the server starts
    gameServer.run = true;

    // Override functions for special virus mechanics
    var self = this;
    Entity.Virus.prototype.onEat = function(prey) {
        // Pushes the virus
        var currBoost = this.boostDistance,
            newBoost = 120,
            bx = currBoost * this.boostDirection.x + newBoost * prey.boostDirection.x,
            by = currBoost * this.boostDirection.y + newBoost * prey.boostDirection.y;
        this.setBoost(Math.sqrt(bx * bx + by * by), Math.atan2(bx, by));
    };
    Entity.MotherCell.prototype.onAdd = function() {
        self.nodesMother.push(this);
    };
    Entity.MotherCell.prototype.onRemove = function() {
        var index = self.nodesMother.indexOf(this);
        if (index != -1)
            self.nodesMother.splice(index, 1);
    };

    // Spawn starting mothercells
    for (var i = 0; i < this.motherMinAmount; i++)
        this.spawnMotherCell(gameServer);
};

Experimental.prototype.onTick = function (gameServer) {
    // Mothercell spawning
    if (gameServer.tickCounter % this.motherSpawnInterval === 1)
        this.spawnMotherCell(gameServer);

    // Mothercell updating
    if (gameServer.tickCounter % 2 === 1)
        for (var i = 0; i < this.nodesMother.length; i++)
            this.nodesMother[i].onUpdate();
};
