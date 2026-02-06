#!/bin/bash

# NetSurf Quick Start Script

echo "=================================="
echo "    NetSurf IDS - Quick Start"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.8+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python found${NC}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}pip3 is not installed. Please install pip3${NC}"
    exit 1
fi
echo -e "${GREEN}✓ pip found${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip3 install -r requirements.txt --break-system-packages

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install dependencies${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check Docker (optional)
echo ""
echo -e "${YELLOW}Checking Docker for Kafka (optional)...${NC}"
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓ Docker found${NC}"
    
    read -p "Do you want to start Kafka with Docker? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Starting Kafka services...${NC}"
        docker-compose up -d
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Kafka started successfully${NC}"
            echo -e "${GREEN}  - Kafka: localhost:9092${NC}"
            echo -e "${GREEN}  - Kafka UI: http://localhost:8080${NC}"
        else
            echo -e "${RED}Failed to start Kafka${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠ Docker not found. Kafka features will be unavailable.${NC}"
    echo -e "${YELLOW}  Install Docker to enable Kafka integration.${NC}"
fi

# Create necessary directories
echo ""
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p uploads saved_models static
echo -e "${GREEN}✓ Directories created${NC}"

# Check for root (for live capture)
echo ""
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠ Not running as root${NC}"
    echo -e "${YELLOW}  Live network capture will require sudo privileges${NC}"
    echo -e "${YELLOW}  Run with: sudo ./start.sh${NC}"
else
    echo -e "${GREEN}✓ Running with root privileges (live capture enabled)${NC}"
fi

# Start the application
echo ""
echo -e "${GREEN}=================================="
echo -e "Starting NetSurf IDS..."
echo -e "==================================${NC}"
echo ""
echo -e "${GREEN}Web Interface: http://localhost:5000${NC}"
echo -e "${GREEN}API Endpoint: http://localhost:5000/api${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

python3 app.py
