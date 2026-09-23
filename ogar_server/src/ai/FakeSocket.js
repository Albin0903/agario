// A fake socket for bot players

function FakeSocket(gameServer) {
    this.server = gameServer;
    this.isBot = true;
    this.isRemoved = false;
}

module.exports = FakeSocket;

// Override

FakeSocket.prototype.sendPacket = function (packet) {
    // Fakes sending a packet
    return;
};

FakeSocket.prototype.close = function (error) {
    while (this.playerTracker.cells.length)
        this.server.removeNode(this.playerTracker.cells[0]);

    this.isRemoved = true;
    var i = this.server.clients.indexOf(this);
    if (i + 1) this.server.clients.splice(i, 1);
    return;
};
