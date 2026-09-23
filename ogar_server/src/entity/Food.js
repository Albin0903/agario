var Cell = require('./Cell');

function Food() {
    Cell.apply(this, Array.prototype.slice.call(arguments));

    this.cellType = 1;
}

module.exports = Food;
Food.prototype = new Cell();

// Main functions
Food.prototype.fromMotherCell = false;

Food.prototype.onAdd = function(gameServer) {
    if (!this.fromMotherCell) gameServer.nodesFood.push(this);
};

Food.prototype.onRemove = function(gameServer) {
    // Remove from list of foods
    var index = gameServer.nodesFood.indexOf(this);
    if (index != -1) gameServer.nodesFood.splice(index, 1);
};
