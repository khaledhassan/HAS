var express = require('express');
var router = express.Router();
var speakeasy = require('speakeasy');
var QRCode = require('qrcode');

//Bad practice, should generate everytime but this works for demo.
var secret_key = "HNSSKRLEOJ6XSXL3NNRVIOBGI4QSUKJVHJRVKL2GFZTVARDONNHA";

// Login index
router.get('/', function(req, res, next){
    // var secret = speakeasy.generateSecret({name: 'HAS'});
    // console.log(secret.base32)
    // qrcode_url = secret.otpauth_url;
    qrcode_url = "otpauth://totp/HAS?secret=" + secret_key;

    // Get the data URL of the authenticator URL
    QRCode.toDataURL(qrcode_url, function (err, data_url) {
        res.render('login', {
            fail: false
        });
    });
});

router.post('/', function (req, res, next) {
    console.log(req.body)
    var userToken = req.body.pass;
    var base32secret = secret_key;

    var secret = speakeasy.generateSecret();

    // Use verify() to check the token against the secret
    var verified = speakeasy.totp.verify({
        secret: base32secret,
        encoding: 'base32',
        token: userToken
    });

    if (verified == true) {//login succeeds
        req.session.logined = true;
        res.redirect('/door');
    } else {
        res.render('login', {
            fail: true
        });
    }
})

router.get('/logout', function (req, res, next) {
    req.session.logined = undefined;
    res.redirect('/');
})

// Show the QRCODE for user to add to Google Authenticator.
router.get('/qrcode', function (req, res, next) {

    qrcode_url = "otpauth://totp/HAS?secret=" + secret_key;
    // Get the data URL of the authenticator URL
    QRCode.toDataURL(qrcode_url, function (err, data_url) {
        res.render('qrcode', {
            qrcode_base64: data_url
        });
    });
});


module.exports = router;
