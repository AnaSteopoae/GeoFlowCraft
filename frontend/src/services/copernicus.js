import axios from "axios";

const API_URL = `${import.meta.env.VITE_COPERNICUS_SERVICE_API_URL}`;

export default {
    async search(geojson, startDate, endDate) {
        let response = await axios.post(`${API_URL}/search`, {
            start_date: startDate,
            end_date: endDate,
            geojson: geojson
        });

        return response.data;
    },

    async download(items) {
        let response = await axios.post(`${API_URL}/download`, {
            items: items
        });

        return response.data;
    },

    async getDownloadStatus(taskId) {
        let response = await axios.get(`${API_URL}/status/${taskId}`);

        return response.data;
    },

    async checkS1Availability(bbox, targetDate, daysTolerance = 6) {
        let response = await axios.post(`${API_URL}/check/s1`, {
            bbox: bbox,
            target_date: targetDate,
            days_tolerance: daysTolerance
        });
        return response.data;
    },

    async checkOverlap(path1, path2) {
        let response = await axios.post(`${API_URL}/check/overlap`, {
            path1: path1,
            path2: path2
        });
        return response.data;
    },

    async getGeotiffBbox(filePath) {
        let response = await axios.post(`${API_URL}/check/bbox`, { path: filePath });
        return response.data;
    }
}