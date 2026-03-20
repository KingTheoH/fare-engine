#!/bin/bash
set -e

echo "🛫 Setting up Cheap Flight Finder..."

# Create .env if not present
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Created .env — add your API keys before searching."
fi

# Install Node deps
echo "📦 Installing Node dependencies..."
npm install

# Prisma
echo "🗄️  Setting up SQLite database..."
npx prisma db push

# Python deps
echo "🐍 Installing Python dependencies..."
pip3 install -r scripts/requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next: Add your free API keys to .env:"
echo "   KIWI_API_KEY  → https://tequila.kiwi.com/portal/login"
echo "   SERPAPI_KEY   → https://serpapi.com"
echo ""
echo "▶️  Then run: npm run dev"
echo "   Open:     http://localhost:3002"
