#!/bin/bash

# Google Cloud Setup Script for LLM-Driven Artist Recommendation Engine
# This script enables required APIs and creates the Firestore database

set -e

echo "🚀 Setting up Google Cloud for LLM-Driven Artist Recommendation Engine"
echo "=================================================================="

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud CLI (gcloud) is not installed."
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ You are not authenticated with Google Cloud."
    echo "Please run: gcloud auth login"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ No project is set. Please set a project:"
    echo "gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📋 Current project: $PROJECT_ID"
echo ""

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."

APIS=(
    "run.googleapis.com"                    # Cloud Run
    "cloudfunctions.googleapis.com"        # Cloud Functions
    "firestore.googleapis.com"             # Firestore
    "pubsub.googleapis.com"                # Pub/Sub
    "monitoring.googleapis.com"            # Cloud Monitoring
    "logging.googleapis.com"               # Cloud Logging
    "cloudbuild.googleapis.com"            # Cloud Build
    "containerregistry.googleapis.com"     # Container Registry
    "iam.googleapis.com"                   # Identity and Access Management
    "compute.googleapis.com"               # Compute Engine (for load balancer)
    "storage.googleapis.com"               # Cloud Storage
)

for api in "${APIS[@]}"; do
    echo "  Enabling $api..."
    gcloud services enable "$api" --quiet
done

echo "✅ All APIs enabled successfully!"
echo ""

# Create Firestore database
echo "🗄️  Setting up Firestore database..."

# Check if Firestore database already exists
if gcloud firestore databases list --format="value(name)" | grep -q "projects/$PROJECT_ID/databases/(default)"; then
    echo "✅ Firestore database already exists"
else
    echo "  Creating Firestore database..."
    gcloud firestore databases create --location=us-central1 --quiet
    echo "✅ Firestore database created successfully!"
fi

echo ""

# Create Pub/Sub topic
echo "📢 Setting up Pub/Sub topic..."

TOPIC_NAME="artist-recommendations"
if gcloud pubsub topics list --format="value(name)" | grep -q "$TOPIC_NAME"; then
    echo "✅ Pub/Sub topic '$TOPIC_NAME' already exists"
else
    echo "  Creating Pub/Sub topic '$TOPIC_NAME'..."
    gcloud pubsub topics create "$TOPIC_NAME" --quiet
    echo "✅ Pub/Sub topic created successfully!"
fi

echo ""

# Create service account for the application
echo "👤 Setting up service account..."

SERVICE_ACCOUNT_NAME="artist-recommendation-sa"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

if gcloud iam service-accounts list --format="value(email)" | grep -q "$SERVICE_ACCOUNT_EMAIL"; then
    echo "✅ Service account already exists"
else
    echo "  Creating service account '$SERVICE_ACCOUNT_NAME'..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="Artist Recommendation Service Account" \
        --description="Service account for LLM-Driven Artist Recommendation Engine" \
        --quiet
    
    echo "✅ Service account created successfully!"
fi

# Grant necessary roles to the service account
echo "  Granting roles to service account..."

ROLES=(
    "roles/datastore.user"              # Firestore access
    "roles/pubsub.publisher"           # Pub/Sub publishing
    "roles/pubsub.subscriber"          # Pub/Sub subscription
    "roles/monitoring.metricWriter"    # Cloud Monitoring
    "roles/logging.logWriter"          # Cloud Logging
    "roles/storage.objectViewer"       # Cloud Storage read access
)

for role in "${ROLES[@]}"; do
    echo "    Granting $role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet
done

echo "✅ Service account configured successfully!"
echo ""

# Create and download service account key
echo "🔑 Creating service account key..."

KEY_FILE="service-account-key.json"
if [ -f "$KEY_FILE" ]; then
    echo "✅ Service account key already exists: $KEY_FILE"
else
    echo "  Creating service account key..."
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SERVICE_ACCOUNT_EMAIL" \
        --quiet
    
    echo "✅ Service account key created: $KEY_FILE"
    echo "⚠️  IMPORTANT: Keep this file secure and add it to .gitignore"
fi

echo ""

# Set up environment variables
echo "⚙️  Setting up environment variables..."

ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    echo "✅ .env file already exists"
else
    echo "  Creating .env file from template..."
    cp env.example "$ENV_FILE"
    
    # Update .env with current project
    sed -i.bak "s/your-project-id/$PROJECT_ID/g" "$ENV_FILE"
    sed -i.bak "s|path/to/service-account-key.json|$KEY_FILE|g" "$ENV_FILE"
    
    echo "✅ .env file created and configured"
fi

echo ""

# Verify setup
echo "🔍 Verifying setup..."

echo "  Checking APIs..."
ENABLED_APIS=$(gcloud services list --enabled --format="value(name)" | grep -E "(run|functions|firestore|pubsub|monitoring|logging|build|containerregistry|iam|compute|storage)")
echo "    Enabled APIs: $(echo "$ENABLED_APIS" | wc -l | tr -d ' ')"

echo "  Checking Firestore..."
if gcloud firestore databases list --format="value(name)" | grep -q "projects/$PROJECT_ID/databases/(default)"; then
    echo "    ✅ Firestore database exists"
else
    echo "    ❌ Firestore database not found"
fi

echo "  Checking Pub/Sub topic..."
if gcloud pubsub topics list --format="value(name)" | grep -q "$TOPIC_NAME"; then
    echo "    ✅ Pub/Sub topic exists"
else
    echo "    ❌ Pub/Sub topic not found"
fi

echo "  Checking service account..."
if gcloud iam service-accounts list --format="value(email)" | grep -q "$SERVICE_ACCOUNT_EMAIL"; then
    echo "    ✅ Service account exists"
else
    echo "    ❌ Service account not found"
fi

echo "  Checking service account key..."
if [ -f "$KEY_FILE" ]; then
    echo "    ✅ Service account key exists"
else
    echo "    ❌ Service account key not found"
fi

echo ""
echo "🎉 Google Cloud setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Update your .env file with Algolia and OpenAI API keys"
echo "2. Run: python scripts/seed_data.py"
echo "3. Deploy: gcloud builds submit --config cloudbuild.yaml"
echo "4. Test: python tests/test_api.py"
echo ""
echo "📚 Documentation: README.md"
echo "🔧 Configuration: .env"
echo "🗄️  Database: Firestore in us-central1"
echo "📢 Pub/Sub: artist-recommendations topic"
echo "👤 Service Account: $SERVICE_ACCOUNT_EMAIL" 