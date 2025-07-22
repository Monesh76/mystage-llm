# MyStage - AI Artist Recommendation Frontend

A beautiful, modern web interface for the LLM-Driven Artist Recommendation Engine.

## 🌐 Live Demo

**Frontend URL**: https://artist-recommendation-engine-953523158769.us-central1.run.app/

## ✨ Features

### 🎵 Artist Search
- **Real-time search** by artist name, genre, or style
- **Highlighted results** showing matching terms
- **Rich artist cards** with followers, popularity, and genres
- **Responsive design** that works on all devices

### 🎯 Personalized Recommendations
- **AI-powered recommendations** using GPT-4
- **User preference management** with genre tags
- **Similarity scoring** with detailed reasoning
- **Real-time updates** when preferences change

### 🎨 Modern UI/UX
- **Beautiful gradient design** with glassmorphism effects
- **Smooth animations** and hover effects
- **Toast notifications** for user feedback
- **Loading states** with spinners
- **Mobile-responsive** layout

## 🚀 How to Use

### 1. Search for Artists
1. Enter a search term in the search box (e.g., "rock", "pop", "Taylor Swift")
2. Click the search button or press Enter
3. View highlighted results with artist details

### 2. Set Your Preferences
1. Enter your User ID (default: "user_001")
2. Add or remove favorite genres using the genre tags
3. Click "Save Preferences" to store your choices

### 3. Get AI Recommendations
1. Make sure you have a User ID and saved preferences
2. Click "Get AI Recommendations"
3. View personalized artist suggestions with reasoning

## 🛠️ Technical Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Styling**: Modern CSS with Flexbox/Grid, gradients, and animations
- **Icons**: Font Awesome 6.0
- **Fonts**: Inter (Google Fonts)
- **API**: RESTful API integration with fetch()
- **Deployment**: Google Cloud Run

## 📱 Responsive Design

The frontend is fully responsive and works on:
- **Desktop**: Full-featured experience with hover effects
- **Tablet**: Optimized layout with touch-friendly interactions
- **Mobile**: Stacked layout with mobile-optimized buttons

## 🎨 Design Features

- **Glassmorphism**: Semi-transparent cards with backdrop blur
- **Gradient backgrounds**: Beautiful purple-blue gradients
- **Smooth animations**: Hover effects, transitions, and loading states
- **Color-coded elements**: Different colors for different actions
- **Typography**: Clean, modern font hierarchy

## 🔧 API Integration

The frontend integrates with these API endpoints:

- `GET /api/v1/artists/search` - Artist search
- `POST /api/v1/recommendations` - Get AI recommendations
- `POST /api/v1/preferences` - Save user preferences
- `GET /health` - Health check

## 🚀 Deployment

The frontend is automatically deployed with the main application on Google Cloud Run. The static files are served directly by the Flask application.

## 🎯 User Experience

- **Intuitive interface**: Easy-to-use design with clear call-to-actions
- **Real-time feedback**: Toast notifications for all user actions
- **Loading states**: Visual feedback during API calls
- **Error handling**: Graceful error messages and fallbacks
- **Accessibility**: Keyboard navigation and screen reader support

## 🎵 Sample Usage

1. **Search for "rock"** → Find artists like Olivia Rodrigo with pop rock
2. **Search for "pop"** → Discover Taylor Swift, Ed Sheeran, Ariana Grande
3. **Set preferences** → Add genres like "hip hop", "jazz", "electronic"
4. **Get recommendations** → Receive AI-generated personalized suggestions

## 🔮 Future Enhancements

- **Dark mode** toggle
- **Advanced filters** (country, popularity, followers)
- **Artist comparison** feature
- **Playlist generation** from recommendations
- **Social sharing** of recommendations
- **User authentication** and profiles

---

**Built with ❤️ for music discovery and AI-powered recommendations** 