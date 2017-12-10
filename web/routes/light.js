var express = require('express');
var router = express.Router();

router.use(function(req, res, next) {
    var logined = req.session.logined

    if(logined == undefined)
    {
        res.redirect('/login')
    }else{
        next()
    }

});
/* GET door page. */
router.get('/', function(req, res, next) {
    res.render('light', {

    })
});

module.exports = router;
