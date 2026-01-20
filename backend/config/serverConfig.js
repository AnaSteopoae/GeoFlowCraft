const dotenv = require('dotenv');
dotenv.config();

module.exports = {
    listenPort: process.env.PORT || 5555,
    baseUploadPath: process.env.BASE_UPLOAD_PATH || "./uploads"
}