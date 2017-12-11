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
/* GET ac page. */
router.get('/', function(req, res, next) {
    res.render('ac', {

    })
});

module.exports = router;
