function getInternalError(error) {
    return { 
        success: false, 
        error: error.message ?? `Something went wrong` 
    };
}

function handleError(res, error) {
    console.error('Controller error:', error);
    res.status(500).json(getInternalError(error));
}

module.exports = {
    getInternalError,
    handleError
}