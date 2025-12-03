const dotenv = require('dotenv');
dotenv.config();

module.exports = {
    listenPort: process.env.PORT || 3000,
    baseUploadPath: process.env.BASE_UPLOAD_PATH || "./uploads"
}