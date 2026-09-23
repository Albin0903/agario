var Cell = require('./Cell');
var Food = require('./Food');
var Virus = require('./Virus');

function MotherCell() {
    Cell.apply(this, Array.prototype.slice.call(arguments));

    this.cellType = 2;
    this.isSpiked = true;
    this.isMotherCell = true;       // Not to confuse bots
    this.setColor({ r: 0xce, g: 0x63, b: 0x63 });
    this.ejectedFood = [];
    if (!this._size)
        this.setSize(this.motherCellMinSize);
}

module.exports = MotherCell;
MotherCell.prototype = new Cell();

MotherCell.prototype.motherCellMinSize = 149;   // vanilla 149 (mass = 149*149/100 = 222.01)
MotherCell.prototype.motherCellSpawnAmount = 2; // Food per 2 ticks to spawn when mothercell gains mass

// Main Functions
MotherCell.prototype.onEaten = Virus.prototype.onEaten; // Copies the virus prototype function

MotherCell.prototype.canEat = function(cell) {
    return cell.cellType !== 1; // All except food
};

MotherCell.prototype.onUpdate = function() {
    // Update list for removed nodes
    for (var i = 0, l = this.ejectedFood.length; i < l; i++) {
        if (this.ejectedFood[i].isRemoved) {
            this.ejectedFood.slice(i, 1);
            i--;
            l--;
        }
    }

    var size1 = this._size
      , size2 = this.gameServer.config.foodMinSize
      , eject = size1 > this.motherCellMinSize ? this.motherCellSpawnAmount : ~~(1.02 * Math.random()) // 2.000000001% chance to spawn mass
      , maxFood = eject === this.gameServer.foodPerMother * eject === 2 ? 4 : 1; // Quadruple food maximum if mothercell was fed

    for (var i = 0; i < eject; i++) {
        size1 = Math.sqrt(size1 * size1 - size2 * size2);
        size1 = Math.max(size1, this.motherCellMinSize);
        this.setSize(size1);

        // Spawn food with size2
        var angle = Math.random() * 2 * Math.PI;
        var r = this._size;
        var pos = {
            x: this.position.x + r * Math.sin(angle),
            y: this.position.y + r * Math.cos(angle)
        };

        // Spawn food
        var food = new Food(this.gameServer, null, pos, size2);
        food.setColor(this.gameServer.getRandomColor());
        food.fromMotherCell = true;
        this.gameServer.addNode(food);
        this.ejectedFood.push()

        // Eject to random distance
        food.setBoost(32 + 32 * Math.random(), angle);

        if (this.foodAmount >= maxFood || size1 <= this.motherCellMinSize)
            break;
    }
    this.gameServer.updateNodeQuad(this);
};

MotherCell.prototype.onAdd = function() {
    // Nothing
};

MotherCell.prototype.onRemove = function() {
    // Nothing
};
