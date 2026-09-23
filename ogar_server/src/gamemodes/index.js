module.exports = {
    Mode: require('./Mode'),
    FFA: require('./FFA'),
    Teams: require('./Teams'),
    Experimental: require('./Experimental'),
    RushMode: require('./RushMode'),
    Rainbow: require('./Rainbow'),

    get: function(id) {
        switch (id) {
            case 1: // Teams
                return new module.exports.Teams();
                break;
            case 2: // Experimental
                return new module.exports.Experimental();
                break;
            case 3: // Rainbow
                return new module.exports.Rainbow();
                break;
            case 4: // Rush Mode
                return new module.exports.RushMode();
                break;
            default: // FFA is default
                return new module.exports.FFA();
                break;
        }
    }
};
