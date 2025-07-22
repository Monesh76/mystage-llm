// Global state management
let currentUser = null;
let currentTab = 'discover';
let sessionId = generateSessionId();

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Check authentication status
    checkAuthStatus();
    
    // Initialize event listeners
    initializeEventListeners();
    
    // Initialize tab navigation
    initializeTabNavigation();
    
    // Load initial data for discover tab
    loadDiscoverData();
}

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// ===== TAB NAVIGATION =====
function initializeTabNavigation() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update active tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}Tab`).classList.add('active');
    
    currentTab = tabName;
    
    // Load tab-specific data
    switch(tabName) {
        case 'trending':
            loadTrendingArtists();
            break;
        case 'recommendations':
            loadRecommendationsTab();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

// ===== EVENT LISTENERS =====
function initializeEventListeners() {
    // Search functionality
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Language quick buttons
    document.querySelectorAll('.language-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const language = e.currentTarget.getAttribute('data-language');
            searchByLanguage(language);
        });
    });
    
    // Authentication
    const loginBtn = document.getElementById('loginBtn');
    const registerBtn = document.getElementById('registerBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const analyticsBtn = document.getElementById('analyticsBtn');
    
    if (loginBtn) loginBtn.addEventListener('click', () => showAuthModal('login'));
    if (registerBtn) registerBtn.addEventListener('click', () => showAuthModal('register'));
    if (logoutBtn) logoutBtn.addEventListener('click', logout);
    if (analyticsBtn) analyticsBtn.addEventListener('click', () => switchTab('analytics'));
    
    // Preferences
    const savePreferencesBtn = document.getElementById('savePreferencesBtn');
    if (savePreferencesBtn) savePreferencesBtn.addEventListener('click', savePreferences);
    
    // Recommendations
    const getRecommendationsBtn = document.getElementById('getRecommendationsBtn');
    if (getRecommendationsBtn) getRecommendationsBtn.addEventListener('click', getHybridRecommendations);
    
    // Trending
    const refreshTrendingBtn = document.getElementById('refreshTrendingBtn');
    if (refreshTrendingBtn) refreshTrendingBtn.addEventListener('click', loadTrendingArtists);
    
    // Analytics
    const refreshAnalyticsBtn = document.getElementById('refreshAnalyticsBtn');
    if (refreshAnalyticsBtn) refreshAnalyticsBtn.addEventListener('click', loadAnalytics);
    
    // Preferences inputs
    setupPreferenceInputs();
    
    // Auth form submissions
    setupAuthForms();
}

// ===== SEARCH FUNCTIONALITY =====
async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) {
        showToast('Please enter a search term', 'warning');
        return;
    }
    
    const language = document.getElementById('languageFilter').value;
    const dataSource = document.getElementById('dataSource').value;
    const market = document.getElementById('marketFilter').value;
    
    showLoading('Searching for artists...');
    
    try {
        const params = new URLSearchParams({
            q: query,
            limit: '20'
        });
        
        if (language) params.append('language', language);
        if (market) params.append('market', market);
        if (dataSource) params.append('realtime', dataSource === 'realtime' ? 'true' : 'false');
        
        const headers = getAuthHeaders();
        if (headers.Authorization) {
            headers['X-Session-ID'] = sessionId;
        }
        
        const response = await fetch(`/api/v1/artists/search?${params}`, {
            headers: headers
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displaySearchResults(data);
            updateResultsInfo(data);
        } else {
            showToast(data.error || 'Search failed', 'error');
        }
    } catch (error) {
        console.error('Search error:', error);
        showToast('Search failed. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

async function searchByLanguage(language) {
    document.getElementById('languageFilter').value = language;
    showLoading(`Loading ${language} artists...`);
    
    try {
        const headers = getAuthHeaders();
        if (headers.Authorization) {
            headers['X-Session-ID'] = sessionId;
        }
        
        const response = await fetch(`/api/v1/artists/by-language/${language}?limit=20`, {
            headers: headers
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displaySearchResults({ artists: data.artists, query: `${language} artists` });
            updateResultsInfo(data);
        } else {
            showToast(data.error || 'Failed to load artists', 'error');
        }
    } catch (error) {
        console.error('Language search error:', error);
        showToast('Failed to load artists. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

function displaySearchResults(data) {
    const resultsContainer = document.getElementById('searchResults');
    const artists = data.artists || [];
    
    if (artists.length === 0) {
        resultsContainer.innerHTML = `
            <div class="no-results">
                <i class="fas fa-search"></i>
                <h3>No artists found</h3>
                <p>Try adjusting your search terms or filters</p>
            </div>
        `;
        return;
    }
    
    resultsContainer.innerHTML = artists.map(artist => createArtistCard(artist)).join('');
}

function updateResultsInfo(data) {
    const resultsCount = document.getElementById('resultsCount');
    const dataSourceInfo = document.getElementById('dataSourceInfo');
    
    resultsCount.textContent = `${data.total_count || 0} results`;
    
    if (data.real_time_data) {
        dataSourceInfo.textContent = 'Real-time data';
        dataSourceInfo.style.background = 'rgba(46, 204, 113, 0.1)';
        dataSourceInfo.style.color = '#2ecc71';
    } else {
        dataSourceInfo.textContent = 'Cached data';
        dataSourceInfo.style.background = 'rgba(52, 152, 219, 0.1)';
        dataSourceInfo.style.color = '#3498db';
    }
}

// ===== TRENDING ARTISTS =====
async function loadTrendingArtists() {
    const market = document.getElementById('trendingMarket').value || 'US';
    showLoading('Loading trending artists...');
    
    try {
        const response = await fetch(`/api/v1/artists/trending?market=${market}&limit=20`);
        const data = await response.json();
        
        if (response.ok) {
            displayTrendingResults(data.artists);
        } else {
            showToast(data.error || 'Failed to load trending artists', 'error');
        }
    } catch (error) {
        console.error('Trending artists error:', error);
        showToast('Failed to load trending artists', 'error');
    } finally {
        hideLoading();
    }
}

function displayTrendingResults(artists) {
    const container = document.getElementById('trendingResults');
    
    if (!artists || artists.length === 0) {
        container.innerHTML = `
            <div class="no-results">
                <i class="fas fa-fire"></i>
                <h3>No trending data available</h3>
                <p>Try selecting a different market</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = artists.map((artist, index) => {
        const card = createArtistCard(artist);
        // Add trending rank
        return card.replace('<div class="artist-card"', 
            `<div class="artist-card trending-rank-${index + 1}"`);
    }).join('');
}

// ===== RECOMMENDATIONS =====
function loadRecommendationsTab() {
    if (!currentUser) {
        return; // Login prompt is already shown
    }
    
    // Load user predictions
    loadUserPredictions();
}

async function loadUserPredictions() {
    try {
        const response = await fetch('/api/v1/predictions/user-preferences', {
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayPredictions(data.predictions);
        }
    } catch (error) {
        console.error('Predictions error:', error);
    }
}

function displayPredictions(predictions) {
    const container = document.getElementById('predictionsContent');
    
    if (!predictions || Object.keys(predictions).length === 0) {
        container.innerHTML = '<p>No predictions available yet. Interact with the app to generate predictions!</p>';
        return;
    }
    
    let html = '';
    
    // Predicted genres
    if (predictions.predicted_genres && predictions.predicted_genres.length > 0) {
        html += `
            <div class="prediction-item">
                <div class="prediction-type">You might like these genres:</div>
                <div class="prediction-details">
                    ${predictions.predicted_genres.map(genre => `
                        <div class="prediction-detail">
                            <span>${genre.genre}</span>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${genre.confidence * 100}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    // Predicted languages
    if (predictions.predicted_languages && predictions.predicted_languages.length > 0) {
        html += `
            <div class="prediction-item">
                <div class="prediction-type">You might enjoy music in:</div>
                <div class="prediction-details">
                    ${predictions.predicted_languages.map(lang => `
                        <div class="prediction-detail">
                            <span>${lang.language}</span>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${lang.confidence * 100}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    // Predicted artists
    if (predictions.predicted_artists && predictions.predicted_artists.length > 0) {
        html += `
            <div class="prediction-item">
                <div class="prediction-type">Artists similar users liked:</div>
                <div class="prediction-details">
                    ${predictions.predicted_artists.slice(0, 3).map(artist => `
                        <div class="prediction-detail">
                            <span>${artist.artist}</span>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${artist.confidence * 100}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    // Reasoning
    if (predictions.reasoning && predictions.reasoning.length > 0) {
        html += `
            <div class="prediction-item">
                <div class="prediction-type">AI Insights:</div>
                <ul class="insights-list">
                    ${predictions.reasoning.map(reason => `<li>${reason}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    container.innerHTML = html || '<p>Building your music profile... Check back after more interactions!</p>';
}

async function getHybridRecommendations() {
    if (!currentUser) {
        showToast('Please log in to get recommendations', 'warning');
        return;
    }
    
    showLoading('Generating AI recommendations...');
    
    try {
        const language = document.getElementById('recommendationLanguage').value;
        const includeTrending = document.getElementById('includeTrending').checked;
        
        const requestData = {
            limit: 10,
            include_trending: includeTrending
        };
        
        if (language) {
            requestData.language = language;
        }
        
        const response = await fetch('/api/v1/recommendations/hybrid', {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json',
                'X-Session-ID': sessionId
            },
            body: JSON.stringify(requestData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.recommendations && data.recommendations.length > 0) {
                displayRecommendations(data.recommendations);
                showToast('AI recommendations generated successfully!', 'success');
            } else {
                displayNoRecommendationsGuidance();
                showToast('No recommendations yet. Try interacting more with the app!', 'info');
            }
        } else {
            showToast(data.error || 'Failed to get recommendations', 'error');
        }
    } catch (error) {
        console.error('Recommendations error:', error);
        showToast('Failed to get recommendations', 'error');
    } finally {
        hideLoading();
    }
}

function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendationsList');
    container.innerHTML = recommendations.map(rec => createRecommendationCard(rec)).join('');
}

function displayNoRecommendationsGuidance() {
    const container = document.getElementById('recommendationsList');
    container.innerHTML = `
        <div class="no-recommendations-guidance">
            <div class="guidance-icon">🎵</div>
            <h3>Build Your Music Profile</h3>
            <p>To get personalized AI recommendations, try these actions:</p>
            <div class="guidance-steps">
                <div class="step">
                    <span class="step-icon">🔍</span>
                    <span>Search for artists you like in the Discover tab</span>
                </div>
                <div class="step">
                    <span class="step-icon">📊</span>
                    <span>Browse and view trending artists</span>
                </div>
                <div class="step">
                    <span class="step-icon">⚙️</span>
                    <span>Set your music preferences above</span>
                </div>
                <div class="step">
                    <span class="step-icon">🎯</span>
                    <span>Choose genres and languages you enjoy</span>
                </div>
            </div>
            <p class="guidance-note">The more you interact, the better your recommendations become!</p>
        </div>
    `;
}

function createRecommendationCard(recommendation) {
    const confidencePercentage = (recommendation.confidence * 100).toFixed(0);
    
    return `
        <div class="artist-card recommendation-card" data-recommendation-id="${recommendation.artist_id}">
            <div class="artist-header">
                <div class="artist-image-placeholder"></div>
                <div class="artist-info">
                    <h3>${recommendation.artist_name}</h3>
                    <div class="confidence-score">${confidencePercentage}% match</div>
                </div>
            </div>
            <div class="artist-details">
                <div class="detail-row">
                    <span class="detail-label">Genres:</span>
                    <div class="genre-list">
                        ${recommendation.genres.map(genre => `<span class="genre-tag">${genre}</span>`).join('')}
                    </div>
                </div>
                <div class="detail-row">
                    <span class="detail-label">AI Reasoning:</span>
                    <span class="detail-value">${recommendation.reasoning}</span>
                </div>
            </div>
            <div class="recommendation-actions">
                <button class="btn btn-sm btn-primary" onclick="showFeedbackModal('${recommendation.artist_id}', '${recommendation.artist_name}')">
                    <i class="fas fa-thumbs-up"></i> Rate
                </button>
            </div>
        </div>
    `;
}

// ===== ANALYTICS =====
async function loadAnalytics() {
    if (!currentUser) {
        return;
    }
    
    const timeframe = document.getElementById('analyticsTimeframe').value || '30';
    showLoading('Loading analytics...');
    
    try {
        const response = await fetch(`/api/v1/analytics/user-behavior?days=${timeframe}`, {
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayAnalytics(data);
        } else {
            showToast(data.error || 'Failed to load analytics', 'error');
        }
    } catch (error) {
        console.error('Analytics error:', error);
        showToast('Failed to load analytics', 'error');
    } finally {
        hideLoading();
    }
}

function displayAnalytics(data) {
    const container = document.getElementById('analyticsContent');
    const behavior = data.behavior_patterns || {};
    const predictions = data.predictions || {};
    
    container.innerHTML = `
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-mouse-pointer"></i>
                <span>Total Interactions</span>
            </div>
            <div class="widget-value">${behavior.total_interactions || 0}</div>
            <div class="widget-label">in the last ${data.period_days} days</div>
        </div>
        
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-compass"></i>
                <span>Discovery Rate</span>
            </div>
            <div class="widget-value">${((behavior.discovery_rate || 0) * 100).toFixed(1)}%</div>
            <div class="widget-label">of interactions led to discoveries</div>
        </div>
        
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-music"></i>
                <span>Top Genres</span>
            </div>
            <div class="top-genres">
                ${Object.entries(behavior.genre_preferences || {})
                    .sort(([,a], [,b]) => b - a)
                    .slice(0, 5)
                    .map(([genre, count]) => `
                        <div class="genre-stat">
                            <span class="genre-name">${genre}</span>
                            <span class="genre-count">${count}</span>
                        </div>
                    `).join('') || '<p>No genre data yet</p>'}
            </div>
        </div>
        
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-globe"></i>
                <span>Language Preferences</span>
            </div>
            <div class="language-preferences">
                ${Object.entries(behavior.language_preferences || {})
                    .sort(([,a], [,b]) => b - a)
                    .slice(0, 3)
                    .map(([lang, count]) => `
                        <div class="language-stat">
                            <span class="language-name">${lang}</span>
                            <span class="language-count">${count} artists</span>
                        </div>
                    `).join('') || '<p>No language data yet</p>'}
            </div>
        </div>
        
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-lightbulb"></i>
                <span>AI Insights</span>
            </div>
            <ul class="insights-list">
                ${data.insights && data.insights.length > 0 ? 
                    data.insights.map(insight => `<li>${insight}</li>`).join('') :
                    '<li>Keep using the app to generate insights!</li>'}
            </ul>
        </div>
        
        <div class="analytics-widget">
            <div class="widget-header">
                <i class="fas fa-clock"></i>
                <span>Activity Pattern</span>
            </div>
            <div class="activity-pattern">
                ${behavior.listening_times && behavior.listening_times.length > 0 ? 
                    `<p>Most active during ${getMostActiveTime(behavior.listening_times)}</p>` :
                    '<p>No activity pattern data yet</p>'}
            </div>
        </div>
    `;
}

function getMostActiveTime(listeningTimes) {
    const hourCounts = {};
    listeningTimes.forEach(hour => {
        hourCounts[hour] = (hourCounts[hour] || 0) + 1;
    });
    
    const mostActiveHour = Object.entries(hourCounts)
        .sort(([,a], [,b]) => b - a)[0];
    
    if (!mostActiveHour) return 'various times';
    
    const hour = parseInt(mostActiveHour[0]);
    const timeRanges = {
        morning: [6, 11],
        afternoon: [12, 17],
        evening: [18, 21],
        night: [22, 5]
    };
    
    for (const [period, [start, end]] of Object.entries(timeRanges)) {
        if ((start <= end && hour >= start && hour <= end) ||
            (start > end && (hour >= start || hour <= end))) {
            return period;
        }
    }
    
    return 'various times';
}

// ===== FEEDBACK SYSTEM =====
function showFeedbackModal(artistId, artistName) {
    const modal = document.getElementById('feedbackModal');
    const artistInfo = document.getElementById('feedbackArtistInfo');
    
    artistInfo.innerHTML = `
        <h4>${artistName}</h4>
        <p>Help us improve our recommendations by rating this suggestion</p>
    `;
    
    // Store current recommendation data
    modal.setAttribute('data-artist-id', artistId);
    modal.setAttribute('data-artist-name', artistName);
    
    modal.style.display = 'block';
    
    // Setup feedback buttons
    setupFeedbackButtons();
}

function setupFeedbackButtons() {
    document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.onclick = async (e) => {
            const feedback = e.currentTarget.getAttribute('data-feedback');
            await submitFeedback(feedback);
        };
    });
}

async function submitFeedback(feedback) {
    const modal = document.getElementById('feedbackModal');
    const artistId = modal.getAttribute('data-artist-id');
    const artistName = modal.getAttribute('data-artist-name');
    
    try {
        const response = await fetch('/api/v1/feedback/recommendation', {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recommendation_id: artistId,
                feedback: feedback,
                artist_data: {
                    name: artistName,
                    artist_id: artistId
                }
            })
        });
        
        if (response.ok) {
            showToast('Thank you for your feedback!', 'success');
            closeFeedbackModal();
        } else {
            showToast('Failed to submit feedback', 'error');
        }
    } catch (error) {
        console.error('Feedback error:', error);
        showToast('Failed to submit feedback', 'error');
    }
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').style.display = 'none';
}

// ===== ARTIST CARD CREATION =====
function createArtistCard(artist) {
    const popularity = artist.popularity || 0;
    const followers = formatFollowers(artist.followers || 0);
    const genres = artist.genres || [];
    const imageUrl = artist.image_url || '';
    
    return `
        <div class="artist-card fade-in">
            <div class="artist-header">
                ${imageUrl ? 
                    `<img src="${imageUrl}" alt="${artist.name}" class="artist-image" onerror="this.style.display='none'">` :
                    '<div class="artist-image"></div>'
                }
                <div class="artist-info">
                    <h3>${artist.name}</h3>
                    ${artist.language ? `<p class="artist-language">${artist.language}</p>` : ''}
                </div>
            </div>
            <div class="artist-details">
                <div class="detail-row">
                    <span class="detail-label">Popularity:</span>
                    <span class="detail-value">${popularity}/100</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Followers:</span>
                    <span class="detail-value">${followers}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Genres:</span>
                    <div class="genre-list">
                        ${genres.slice(0, 3).map(genre => `<span class="genre-tag">${genre}</span>`).join('')}
                    </div>
                </div>
                ${artist.spotify_url ? `
                    <div class="detail-row">
                        <a href="${artist.spotify_url}" target="_blank" class="btn btn-sm btn-secondary">
                            <i class="fab fa-spotify"></i> View on Spotify
                        </a>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function formatFollowers(count) {
    if (count >= 1000000) {
        return (count / 1000000).toFixed(1) + 'M';
    } else if (count >= 1000) {
        return (count / 1000).toFixed(1) + 'K';
    }
    return count.toString();
}

// ===== PREFERENCES MANAGEMENT =====
function setupPreferenceInputs() {
    // Genre input
    const genreInput = document.getElementById('newGenre');
    if (genreInput) {
        genreInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addGenreTag(e.target.value.trim());
                e.target.value = '';
            }
        });
    }
    
    // Mood input
    const moodInput = document.getElementById('newMood');
    if (moodInput) {
        moodInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addMoodTag(e.target.value.trim());
                e.target.value = '';
            }
        });
    }
    
    // Language select
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                addLanguageTag(e.target.value);
                e.target.value = '';
            }
        });
    }
}

function addGenreTag(genre) {
    if (!genre) return;
    
    const container = document.getElementById('genreTags');
    const tag = document.createElement('span');
    tag.className = 'genre-tag';
    tag.innerHTML = `${genre} <i class="fas fa-times" onclick="removeTag(this)"></i>`;
    container.appendChild(tag);
}

function addMoodTag(mood) {
    if (!mood) return;
    
    const container = document.getElementById('moodTags');
    const tag = document.createElement('span');
    tag.className = 'mood-tag';
    tag.innerHTML = `${mood} <i class="fas fa-times" onclick="removeTag(this)"></i>`;
    container.appendChild(tag);
}

function addLanguageTag(language) {
    if (!language) return;
    
    const container = document.getElementById('languageTags');
    
    // Check if language already exists
    const existing = container.querySelector(`[data-language="${language}"]`);
    if (existing) return;
    
    const tag = document.createElement('span');
    tag.className = 'language-tag';
    tag.setAttribute('data-language', language);
    tag.innerHTML = `${language} <i class="fas fa-times" onclick="removeTag(this)"></i>`;
    container.appendChild(tag);
}

function removeTag(element) {
    element.parentElement.remove();
}

async function savePreferences() {
    if (!currentUser) {
        showToast('Please log in to save preferences', 'warning');
        return;
    }
    
    const genres = Array.from(document.querySelectorAll('#genreTags .genre-tag'))
        .map(tag => tag.textContent.replace('×', '').trim());
    
    const moods = Array.from(document.querySelectorAll('#moodTags .mood-tag'))
        .map(tag => tag.textContent.replace('×', '').trim());
    
    const languages = Array.from(document.querySelectorAll('#languageTags .language-tag'))
        .map(tag => tag.getAttribute('data-language'));
    
    const preferences = {
        favorite_genres: genres,
        mood_preferences: moods,
        language_preferences: languages
    };
    
    showLoading('Saving preferences...');
    
    try {
        const response = await fetch('/api/v1/preferences', {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(preferences)
        });
        
        if (response.ok) {
            showToast('Preferences saved successfully!', 'success');
        } else {
            const data = await response.json();
            showToast(data.error || 'Failed to save preferences', 'error');
        }
    } catch (error) {
        console.error('Save preferences error:', error);
        showToast('Failed to save preferences', 'error');
    } finally {
        hideLoading();
    }
}

async function loadUserPreferences() {
    if (!currentUser) return;
    
    try {
        const response = await fetch('/api/v1/preferences', {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            populatePreferences(data.preferences);
        }
    } catch (error) {
        console.error('Load preferences error:', error);
    }
}

function populatePreferences(preferences) {
    // Clear existing tags
    document.getElementById('genreTags').innerHTML = '';
    document.getElementById('moodTags').innerHTML = '';
    document.getElementById('languageTags').innerHTML = '';
    
    // Add genres
    preferences.favorite_genres?.forEach(genre => addGenreTag(genre));
    
    // Add moods
    preferences.mood_preferences?.forEach(mood => addMoodTag(mood));
    
    // Add languages
    preferences.language_preferences?.forEach(language => addLanguageTag(language));
}

// ===== AUTHENTICATION =====
function setupAuthForms() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    const loginSubmitBtn = document.getElementById('loginSubmitBtn');
    
    if (loginSubmitBtn) {
        loginSubmitBtn.addEventListener('click', handleLogin);
    }
    
    // Register form
    const registerSubmitBtn = document.getElementById('registerSubmitBtn');
    
    if (registerSubmitBtn) {
        registerSubmitBtn.addEventListener('click', handleRegister);
    }
    
    // Google auth buttons
    const googleLoginBtn = document.getElementById('googleLoginBtn');
    const googleRegisterBtn = document.getElementById('googleRegisterBtn');
    
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', () => window.location.href = '/api/auth/google');
    }
    
    if (googleRegisterBtn) {
        googleRegisterBtn.addEventListener('click', () => window.location.href = '/api/auth/google');
    }
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    if (!email || !password) {
        showToast('Please fill in all fields', 'warning');
        return;
    }
    
    showLoading('Logging in...');
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('authToken', data.token);
            currentUser = { 
                token: data.token,
                user_id: data.user_id || data.user?.user_id
            };
            updateAuthUI();
            closeAuthModal();
            showToast('Login successful!', 'success');
            
            // Load user data
            loadUserPreferences();
            if (currentTab === 'recommendations') {
                loadUserPredictions();
            }
        } else {
            showToast(data.error || 'Login failed', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showToast('Login failed. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

async function handleRegister() {
    const email = document.getElementById('registerEmail').value;
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (!email || !username || !password || !confirmPassword) {
        showToast('Please fill in all fields', 'warning');
        return;
    }
    
    if (password !== confirmPassword) {
        showToast('Passwords do not match', 'warning');
        return;
    }
    
    showLoading('Creating account...');
    
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('authToken', data.token);
            currentUser = { 
                token: data.token,
                user_id: data.user_id || data.user?.user_id
            };
            updateAuthUI();
            closeAuthModal();
            showToast('Account created successfully!', 'success');
        } else {
            showToast(data.error || 'Registration failed', 'error');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showToast('Registration failed. Please try again.', 'error');
    } finally {
        hideLoading();
    }
}

function checkAuthStatus() {
    const token = localStorage.getItem('authToken');
    if (token) {
        // Verify token with server
        fetch('/api/v1/preferences', {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                localStorage.removeItem('authToken');
                throw new Error('Token invalid');
            }
        })
        .then(data => {
            currentUser = { token };
            updateAuthUI();
            loadUserPreferences();
        })
        .catch(() => {
            localStorage.removeItem('authToken');
            currentUser = null;
            updateAuthUI();
        });
    }
}

function updateAuthUI() {
    const authButtons = document.getElementById('authButtons');
    const userProfile = document.getElementById('userProfile');
    const loginPrompt = document.getElementById('loginPrompt');
    const preferencesForm = document.getElementById('preferencesForm');
    const recommendationsLoginPrompt = document.getElementById('recommendationsLoginPrompt');
    const recommendationsContent = document.getElementById('recommendationsContent');
    const analyticsTab = document.querySelector('[data-tab="analytics"]');
    
    if (currentUser) {
        authButtons.style.display = 'none';
        userProfile.style.display = 'flex';
        loginPrompt.style.display = 'none';
        preferencesForm.style.display = 'block';
        recommendationsLoginPrompt.style.display = 'none';
        recommendationsContent.style.display = 'block';
        analyticsTab.style.display = 'flex';
        
        // Update user info with actual data
        if (currentUser.user_id) {
            const username = currentUser.user_id.split('@')[0];
            document.getElementById('userName').textContent = username;
            document.getElementById('userEmail').textContent = currentUser.user_id;
        } else {
            document.getElementById('userName').textContent = 'User';
            document.getElementById('userEmail').textContent = 'user@example.com';
        }
    } else {
        authButtons.style.display = 'flex';
        userProfile.style.display = 'none';
        loginPrompt.style.display = 'block';
        preferencesForm.style.display = 'none';
        recommendationsLoginPrompt.style.display = 'block';
        recommendationsContent.style.display = 'none';
        analyticsTab.style.display = 'none';
    }
}

function logout() {
    localStorage.removeItem('authToken');
    currentUser = null;
    updateAuthUI();
    
    // Clear preference forms
    document.getElementById('genreTags').innerHTML = '';
    document.getElementById('moodTags').innerHTML = '';
    document.getElementById('languageTags').innerHTML = '';
    
    showToast('Logged out successfully', 'success');
    
    // Switch to discover tab
    switchTab('discover');
}

function getAuthHeaders() {
    const token = localStorage.getItem('authToken');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// ===== MODAL MANAGEMENT =====
function showAuthModal(type) {
    const modal = document.getElementById('authModal');
    const modalTitle = document.getElementById('authModalTitle');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (type === 'login') {
        modalTitle.textContent = 'Login';
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        modalTitle.textContent = 'Create Account';
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
    
    modal.style.display = 'block';
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

function switchToRegister() {
    showAuthModal('register');
}

function switchToLogin() {
    showAuthModal('login');
}

// ===== UTILITY FUNCTIONS =====
function showLoading(message = 'Loading...') {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    loadingText.textContent = message;
    overlay.style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="toast-close">×</button>
        </div>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

function loadDiscoverData() {
    // Optional: Load some initial data for the discover tab
    // This could be featured artists or recent searches
}

// Close modals when clicking outside
window.addEventListener('click', (e) => {
    const authModal = document.getElementById('authModal');
    const feedbackModal = document.getElementById('feedbackModal');
    
    if (e.target === authModal) {
        closeAuthModal();
    }
    if (e.target === feedbackModal) {
        closeFeedbackModal();
    }
});

// Handle ESC key to close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAuthModal();
        closeFeedbackModal();
    }
}); 






