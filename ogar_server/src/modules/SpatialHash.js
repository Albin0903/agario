function SpatialHash(bound, bucketSize) {
    this.bucketSize = bucketSize || 100;
    this.bound = bound;

    this.init();
}

module.exports = SpatialHash;

SpatialHash.prototype.init = function() {
    var b = this.bound,
        bucketSize = this.bucketSize;

    this._hStart = ~~(b.minx / bucketSize);
    this._hEnd = ~~(b.maxx / bucketSize);
    this._vStart = ~~(b.miny / bucketSize);
    this._vEnd = ~~(b.maxy / bucketSize);

    var z = { };
    var i = this._hStart;
    for (; i <= this._hEnd; i++) {
        var j = this._vStart,
            a = { };

        for (; j <= this._vEnd; j++)
            a[j] = [];
        z[i] = a;
    }

    this.hashes = z;
    this.itemCount = 0;
    this.horizontalBuckets = (this._hEnd - this._hStart) + 1;
    this.verticalBuckets = (this._vEnd - this._vStart) + 1;
    this.bucketCount = this.horizontalBuckets * this.verticalBuckets;
    this._nId = -9e15;
};

SpatialHash.prototype.insert = function(item) {
    if (!item.bound) return;
    var b = item.bound,
        bucketSize = this.bucketSize;

    var hStart = Math.max(~~(b.minx / bucketSize), this._hStart);
    var hEnd = Math.min(~~(b.maxx / bucketSize), this._hEnd);
    var vStart = Math.max(~~(b.miny / bucketSize), this._vStart);
    var vEnd = Math.min(~~(b.maxy / bucketSize), this._vEnd);
    item.__b = {
        hStart: hStart,
        hEnd: hEnd,
        vStart: vStart,
        vEnd: vEnd,
        id: this._nId++
    };

    var i = hStart, j;
    for (; i <= hEnd; i++) {
        j = vStart;
        for (; j <= vEnd; j++)
            this.hashes[i][j].push(item);
    }

    if (this.itemCount++ >= 9e15)
        throw new Error("SpatialHash: To ensure pure integer stability it must not have more than 9E15 (900 000 000 000 000) objects");
    else if (this._nId > 9e15 - 1)
        this._nId = -9e15;
};

SpatialHash.prototype.remove = function(item) {
    if (!item.__b) return;

    var hStart = item.__b.hStart;
    var hEnd = item.__b.hEnd;
    var vStart = item.__b.vStart;
    var vEnd = item.__b.vEnd;

    var i = hStart, j, k;
    for (; i <= hEnd; i++) {
        j = vStart;
        for (; j <= vEnd; j++) {
            k = this.hashes[i][j].indexOf(item);
            if (k !== -1) {
                this.hashes[i][j].splice(k, 1);
            }
        }
    }

    if (!(delete item.__b)) item.__b = undefined;
    this.itemCount--;
};

SpatialHash.prototype.update = function(item) {
    this.remove(item);
    this.insert(item);
};

SpatialHash.prototype.__srch = function(bound, selector, callback, returnOnFirst) {
    var b = bound,
        bucketSize = this.bucketSize;

    // bound might be larger than the hash's size itself
    var hStart = Math.max(~~(b.minx / bucketSize), this._hStart);
    var hEnd = Math.min(~~(b.maxx / bucketSize), this._hEnd);
    var vStart = Math.max(~~(b.miny / bucketSize), this._vStart);
    var vEnd = Math.min(~~(b.maxy / bucketSize), this._vEnd);

    var i = hStart, j, k, l, m, o = [], p = [];
    for (; i <= hEnd; i++) {
        j = vStart;
        for (; j <= vEnd; j++) {
            k = this.hashes[i][j];
            l = k.length;
            m = 0;
            for (; m < l; m++) {
                if (!k[m]) continue;
                if (intersects(k[m].bound, bound) && p.indexOf(k[m].__b.id) === -1) {
                    p.push(k[m].__b.id);
                    if (selector) if (!selector(k[m])) continue;
                    if (callback) callback(k[m]);
                    if (returnOnFirst) return true;
                    o.push(k[m]);
                }
            }
        }
    }
    if (returnOnFirst) return false;
    return o;
};

SpatialHash.prototype.any = function(bound) {
    return this.__srch(bound, null, null, true);
};

SpatialHash.prototype.query = function(bound, selector) {
    return this.__srch(bound, selector, null, false);
};

SpatialHash.prototype.find = function(bound, callback) {
    return this.__srch(bound, null, callback, false);
};

function intersects(a, b) {
    return a.minx <= b.maxx ||
        a.maxx >= b.minx ||
        a.miny <= b.maxy ||
        a.maxy >= b.miny;
}

function getBounds(a) {
    return {
        left: a.minx,
        right: a.maxx,
        top: a.miny,
        bottom: a.maxy
    };
}
