import { defineStore } from "pinia";
import aiService from "@/services/aiService";

export default defineStore('aiAgent', {
    state: () => ({
        availableAgents: [],
        selectedAgent: null,
        isLoading: false,
        error: null
    }),
    getters: {
        /**
         * Returnează agentul selectat cu toate detaliile
         */
        getSelectedAgent: (state) => {
            return state.availableAgents.find(agent => agent.id === state.selectedAgent);
        },
        
        /**
         * Verifică dacă există agenți disponibili
         */
        hasAgents: (state) => {
            return state.availableAgents.length > 0;
        }
    },
    actions: {
        /**
         * Încarcă lista de agenți AI disponibili
         */
        async loadAvailableAgents() {
            this.isLoading = true;
            this.error = null;
            
            try {
                const response = await aiService.getAvailableAgents();
                
                if (response.success) {
                    this.availableAgents = response.agents;
                    
                    // Selectează primul agent by default dacă există
                    if (this.availableAgents.length > 0 && !this.selectedAgent) {
                        this.selectedAgent = this.availableAgents[0].id;
                    }
                }
            } catch (error) {
                this.error = error.message;
                console.error('Eroare la încărcarea agenților AI:', error);
            } finally {
                this.isLoading = false;
            }
        },
        
        /**
         * Setează agentul selectat
         */
        setSelectedAgent(agentId) {
            this.selectedAgent = agentId;
        },
        
        /**
         * Verifică starea de sănătate a unui agent
         */
        async checkAgentHealth(agentId) {
            try {
                const response = await aiService.checkAgentHealth(agentId);
                return response.health;
            } catch (error) {
                console.error(`Eroare la verificarea health pentru ${agentId}:`, error);
                return { available: false, error: error.message };
            }
        },
        
        /**
         * Procesează date cu agentul selectat
         */
        async processWithSelectedAgent(inputData) {
            if (!this.selectedAgent) {
                throw new Error('Niciun agent selectat');
            }
            
            try {
                const response = await aiService.processWithAgent(this.selectedAgent, inputData);
                return response;
            } catch (error) {
                console.error('Eroare la procesarea cu AI:', error);
                throw error;
            }
        }
    }
});
