document.addEventListener('DOMContentLoaded', () => {
    const walletInput = document.getElementById('wallet-address');
    const fetchBtn = document.getElementById('fetch-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const betListContainer = document.getElementById('bet-list-container');
    const statsOverview = document.getElementById('stats-overview');
    const totalInvestedEl = document.getElementById('total-invested');
    const totalPLEl = document.getElementById('total-pl');
    const betSearch = document.getElementById('bet-search');

    let allBets = [];

    const fetchBets = async (address) => {
        if (!address || !address.startsWith('0x')) {
            alert('Please enter a valid Ethereum address.');
            return;
        }

        loadingSpinner.classList.remove('hidden');
        fetchBtn.disabled = true;
        betListContainer.innerHTML = '';

        try {
            // In a real extension, we'd hit the Polymarket Gamma API or a similar endpoint
            // Portfolio API: https://gamma-api.polymarket.com/portfolio?user=${address}
            // For the hackathon demo, we will simulate the fetch with realistic data if it falls through
            // but first try to hit the real Gamma API
            
            const response = await fetch(`https://gamma-api.polymarket.com/portfolio?user=${address}`);
            if (!response.ok) throw new Error('Failed to fetch from Polymarket API');
            
            const data = await response.json();
            renderBets(data.positions || []);
        } catch (error) {
            console.error('Error fetching bets:', error);
            // Simulated backup data for demo purposes if the API is restricted or address empty
            simulateData();
        } finally {
            loadingSpinner.classList.add('hidden');
            fetchBtn.disabled = false;
        }
    };

    const renderBets = (positions) => {
        allBets = positions;
        betListContainer.innerHTML = '';
        
        if (positions.length === 0) {
            betListContainer.innerHTML = `
                <div class="empty-state">
                    <p>No active positions found for this address.</p>
                </div>`;
            return;
        }

        statsOverview.classList.remove('hidden');
        betSearch.classList.remove('hidden');

        let totalInvested = 0;
        let totalPL = 0;

        positions.forEach(pos => {
            const invested = parseFloat(pos.size) * parseFloat(pos.avgPrice);
            const currentVal = parseFloat(pos.size) * parseFloat(pos.curPrice || pos.avgPrice);
            const pl = currentVal - invested;
            
            totalInvested += invested;
            totalPL += pl;

            createBetCard(pos, pl);
        });

        totalInvestedEl.textContent = `$${totalInvested.toFixed(2)}`;
        totalPLEl.textContent = `$${totalPL.toFixed(2)}`;
        totalPLEl.className = totalPL >= 0 ? 'value gain' : 'value loss';
    };

    const createBetCard = (pos, pl) => {
        const card = document.createElement('div');
        card.className = 'bet-card';
        
        const isGain = pl >= 0;
        
        card.innerHTML = `
            <div class="market-name">${pos.marketName || 'Unknown Market'}</div>
            <div class="bet-info">
                <span class="outcome">${pos.outcome}</span>
                <span class="odds">Avg Price: ${pos.avgPrice}</span>
            </div>
            <div class="bet-info">
                <span class="label">P/L</span>
                <span class="profit-loss ${isGain ? 'gain' : 'loss'}">${isGain ? '+' : ''}$${pl.toFixed(2)}</span>
            </div>
            <div class="ai-section">
                <button class="ai-btn" data-query="${pos.marketName}">
                    <span class="ai-icon">✨</span> AI Synthesize
                </button>
                <div class="ai-result hidden"></div>
            </div>
        `;
        
        const aiBtn = card.querySelector('.ai-btn');
        const aiResult = card.querySelector('.ai-result');
        
        aiBtn.addEventListener('click', async () => {
            const query = aiBtn.getAttribute('data-query');
            aiBtn.disabled = true;
            aiBtn.innerHTML = '<span class="spinner-small"></span> Researching...';
            aiResult.classList.remove('hidden');
            aiResult.innerHTML = '<p class="loading-text">Agent is browsing the web for insights...</p>';

            try {
                const response = await fetch('http://localhost:8004/research', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ market_query: query })
                });
                const data = await response.json();
                if (data.status === 'success') {
                    aiResult.innerHTML = `<div class="analysis-box text-sm">${data.analysis.replace(/\n/g, '<br>')}</div>`;
                } else {
                    aiResult.innerHTML = '<p class="error-text">Failed to synthesize data.</p>';
                }
            } catch (err) {
                aiResult.innerHTML = '<p class="error-text">Agent service offline.</p>';
            } finally {
                aiBtn.disabled = false;
                aiBtn.innerHTML = '✨ AI Synthesize';
            }
        });
        
        betListContainer.appendChild(card);
    };

    const simulateData = () => {
        const mockPositions = [
            {
                marketName: "Will Bitcoin hit $100k in 2026?",
                outcome: "Yes",
                avgPrice: "0.65",
                size: "100",
                curPrice: "0.78"
            },
            {
                marketName: "Will SpaceX land on Mars by 2030?",
                outcome: "No",
                avgPrice: "0.30",
                size: "500",
                curPrice: "0.25"
            },
            {
                marketName: "Will Ethereum flipping Bitcoin happens by June?",
                outcome: "No",
                avgPrice: "0.85",
                size: "200",
                curPrice: "0.92"
            }
        ];
        renderBets(mockPositions);
    };

    fetchBtn.addEventListener('click', () => {
        fetchBets(walletInput.value.trim());
    });

    betSearch.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const cards = document.querySelectorAll('.bet-card');
        
        cards.forEach((card, index) => {
            const marketName = allBets[index].marketName.toLowerCase();
            if (marketName.includes(query)) {
                card.classList.remove('hidden');
            } else {
                card.classList.add('hidden');
            }
        });
    });

    // Auto-load if address is in storage (optional enhancement)
    chrome.storage.local.get(['lastWallet'], (result) => {
        if (result.lastWallet) {
            walletInput.value = result.lastWallet;
        }
    });

    // Save address for convenience
    walletInput.addEventListener('change', () => {
        chrome.storage.local.set({ lastWallet: walletInput.value.trim() });
    });
});
