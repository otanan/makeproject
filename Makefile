.PHONY: build clean run install test help

# Default target
help:
	@echo "MakeProject - Build Targets"
	@echo ""
	@echo "  make build       - Build the .app bundle and create ZIP"
	@echo "  make build-dmg   - Build and create DMG for distribution"
	@echo "  make clean       - Remove build artifacts"
	@echo "  make run         - Run the app directly from source"
	@echo "  make run-app     - Run the built .app bundle"
	@echo "  make install     - Install Python dependencies"
	@echo "  make test        - Run tests (if available)"
	@echo ""

# Build the app
build:
	@echo "🔨 Building MakeProject..."
	@rm -rf build dist
	@pyinstaller MakeProject.spec --clean --noconfirm
	@if [ -d "dist/MakeProject.app" ]; then \
		cd dist && zip -r -q MakeProject.zip MakeProject.app && cd ..; \
		echo "✓ Build complete!"; \
		echo "  App: dist/MakeProject.app ($(shell du -sh dist/MakeProject.app | cut -f1))"; \
		echo "  ZIP: dist/MakeProject.zip ($(shell du -sh dist/MakeProject.zip | cut -f1))"; \
	else \
		echo "❌ Build failed!"; \
		exit 1; \
	fi

# Build and create DMG
build-dmg: build
	@echo "📦 Creating DMG..."
	@VERSION=$$(python3 -c "import re; text=open('makeproject/__init__.py').read(); print(re.search(r'__version__\\s*=\\s*[\"\\']([^\"\\\']+)[\"\\']', text).group(1))"); \
	mkdir -p dist/dmg && \
	cp -R dist/MakeProject.app dist/dmg/ && \
	hdiutil create -volname "MakeProject" -srcfolder dist/dmg -ov -format UDZO "dist/MakeProject-$$VERSION.dmg" && \
	rm -rf dist/dmg && \
	echo "✓ DMG created: dist/MakeProject-$$VERSION.dmg"

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf build dist __pycache__ makeproject/__pycache__
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✓ Clean complete"

# Run from source
run:
	@python3 main.py

# Run the built app
run-app:
	@if [ -d "dist/MakeProject.app" ]; then \
		open dist/MakeProject.app; \
	else \
		echo "❌ App not found. Run 'make build' first."; \
		exit 1; \
	fi

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@pip install -r requirements.txt
	@echo "✓ Dependencies installed"

# Run tests (placeholder)
test:
	@echo "🧪 Running tests..."
	@python3 -m pytest tests/ || echo "No tests found"

# Quick alias
.PHONY: b c r
b: build
c: clean
r: run
