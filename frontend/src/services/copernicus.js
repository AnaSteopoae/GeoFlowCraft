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
    }
}