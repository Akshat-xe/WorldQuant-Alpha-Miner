/**
 * Quantum Alpha Studio - Local Ollama AI Client
 * Connects directly to local Ollama (http://localhost:11434) via browser fetch
 * 100% Free, Private, and Zero API Token Costs.
 */

const OllamaClient = {
    defaultEndpoint: 'http://localhost:11434',

    async testConnection(endpoint = this.defaultEndpoint) {
        try {
            const res = await fetch(`${endpoint}/api/tags`, { method: 'GET' });
            if (!res.ok) return { connected: false, error: `HTTP ${res.status}` };
            const data = await res.json();
            const models = (data.models || []).map(m => m.name);
            return {
                connected: true,
                models: models.length ? models : ['llama3.2:latest', 'deepseek-r1:latest']
            };
        } catch (e) {
            return {
                connected: false,
                error: 'Cannot connect to Ollama. Make sure Ollama is running (`ollama serve`).'
            };
        }
    },

    async generateAlpha(model = 'deepseek-r1', endpoint = this.defaultEndpoint) {
        const systemPrompt = `You are an expert quantitative researcher writing an alpha for WorldQuant BRAIN.
Output ONLY a valid FastExpr formula lines.
Rules:
1. Operators allowed: rank(), ts_delta(), ts_backfill(), ts_mean(), ts_rank(), power(), group_neutralize().
2. Combine fundamental metrics (e.g. cashflow_op, operating_income, sales, ebitda) with short-term VWAP mean-reversion (e.g. -(close - ts_mean(vwap, 2)) / ts_mean(vwap, 2)).
3. Always wrap with group_neutralize(..., subindustry).
4. No markdown formatting, no explanations, no backticks. Only the code.`;

        const userPrompt = 'Generate a high-Sharpe equity alpha combining cashflow yield, earnings momentum, and 2-day VWAP deviation.';

        try {
            const res = await fetch(`${endpoint}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: model,
                    prompt: `${systemPrompt}\n\n${userPrompt}`,
                    stream: false,
                    options: { temperature: 0.3 }
                })
            });

            if (!res.ok) throw new Error(`Ollama error HTTP ${res.status}`);
            const data = await res.json();
            let rawText = data.response || '';

            // Strip markdown code fences if model output them
            let clean = rawText
                .replace(/```python/gi, '')
                .replace(/```/g, '')
                .replace(/<think>[\s\S]*?<\/think>/gi, '') // Strip DeepSeek-R1 thinking tokens
                .trim();

            return { success: true, formula: clean, model: model };
        } catch (err) {
            return { success: false, error: err.message };
        }
    }
};

window.OllamaClient = OllamaClient;
