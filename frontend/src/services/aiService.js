import axios from 'axios';

const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5555';

export default {
    /**
     * Obține lista tuturor agenților AI disponibili
     */
    async getAvailableAgents() {
        const response = await axios.get(`${API_URL}/api/ai/agents`);
        return response.data;
    },

    /**
     * Verifică starea de sănătate a unui agent
     */
    async checkAgentHealth(agentId) {
        const response = await axios.get(`${API_URL}/api/ai/agents/${agentId}/health`);
        return response.data;
    },

    /**
     * Procesează date cu un agent specific
     */
    async processWithAgent(agentId, inputData) {
        const response = await axios.post(
            `${API_URL}/api/ai/agents/${agentId}/process`,
            inputData
        );
        return response.data;
    },

    /**
     * Procesează o zonă selectată de utilizator
     */
    async processSelectedArea(agentId, areaData) {
        const response = await axios.post(
            `${API_URL}/api/ai/agents/${agentId}/process-area`,
            { areaData }
        );
        return response.data;
    },

    /**
     * Obține modurile SR disponibile (fidelity, balanced, sharp + alpha)
     */
    async getSRModes() {
        const response = await axios.get(`${API_URL}/api/ai/agents/sr-processor/modes`);
        return response.data;
    },

    /**
     * Obține rezultatele procesării pentru un produs specific
     */
    async getProcessingResults(productId) {
        const response = await axios.get(`${API_URL}/api/ai/results/${productId}`);
        return response.data;
    },

    /**
     * Obține toate rezultatele disponibile
     */
    async getAllProcessingResults() {
        const response = await axios.get(`${API_URL}/api/ai/results`);
        return response.data;
    },

    /**
     * Generează URL pentru descărcarea unui fișier rezultat
     */
    getDownloadUrl(filename) {
        return `${API_URL}/api/ai/download/${filename}`;
    }
};