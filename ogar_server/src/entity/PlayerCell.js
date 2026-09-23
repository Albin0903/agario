var Cell = require('./Cell');

function PlayerCell() {
    Cell.apply(this, Array.prototype.slice.call(arguments));
    this.cellType = 0;
    this._canRemerge = false;
}

module.exports = PlayerCell;
PlayerCell.prototype = new Cell();

// Main Functions

PlayerCell.prototype.canEat = function(cell) {
    return true; // player cell can eat anyone
};

PlayerCell.prototype.getSpeed = function(dist) {
    var speed = 2.1106 / Math.pow(this._size, 0.449);
    var normalizedDist = Math.min(dist, 32) * 0.03125;
    speed *= 40 * this.gameServer.config.playerSpeed;
    return speed * normalizedDist / dist;
};

PlayerCell.prototype.onAdd = function(gameServer) {
    gameServer.nodesPlayer.unshift(this);
};

PlayerCell.prototype.onRemove = function(gameServer) {
    // Remove from owned cell list
    var index = this.owner.cells.indexOf(this);
    if (index != -1) {
        this.owner.cells.splice(index, 1);
        // Disable mergeOverride on the last merging cell
        if (this.owner.cells.length <= 2)
            this.owner.mergeOverride = false;
    }

    // Remove from player cell list
    index = gameServer.nodesPlayer.indexOf(this);
    if (index != -1) gameServer.nodesPlayer.splice(index, 1);

    // Gamemode actions
    gameServer.gameMode.onCellRemove(this);
};
