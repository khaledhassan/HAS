var express = require('express');
var router = express.Router();

/* GET home page. */
router.get('/', function(req, res, next) {
  var logined = req.session.logined

  if(logined == undefined)
  {
    res.redirect('/login')
  }else{
      res.redirect('/door')
  }
});

module.exports = router;
