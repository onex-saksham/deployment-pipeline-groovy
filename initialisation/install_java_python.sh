#!/bin/bash
# Usage: ./install_java_python.sh "<python_versions>" "<java_versions>"
# Example: ./install_java_python.sh "3.12.0" "17 21"

set -e

# The first argument is a space-separated string of Python versions
PYTHON_VERSIONS_STRING="$1"
# The second argument is a space-separated string of Java versions
JAVA_VERSIONS_STRING="$2"

echo ">>> Received Python versions to install: [${PYTHON_VERSIONS_STRING}]"
echo ">>> Received Java versions to install: [${JAVA_VERSIONS_STRING}]"

echo ">>> Installing base dependencies..."
sudo apt-get update
sudo apt-get install -y wget curl software-properties-common

# This variable will hold the path of the last Java version installed, to set it as the default JAVA_HOME
LATEST_JAVA_HOME_PATH=""

######################################
#      Install Python Versions       #
######################################
if [ -n "$PYTHON_VERSIONS_STRING" ]; then
    for FULL_PYTHON_VERSION in $PYTHON_VERSIONS_STRING; do
        PYTHON_XY_VERSION=$(echo "$FULL_PYTHON_VERSION" | cut -d. -f1,2)
        echo ">>> Processing Python ${PYTHON_XY_VERSION}..."

        # Check if version is already installed
        if command -v "python${PYTHON_XY_VERSION}" &>/dev/null; then
            echo "--> Python ${PYTHON_XY_VERSION} is already installed. Skipping installation."
        else
            echo "--> Attempting to install Python ${PYTHON_XY_VERSION} from APT..."

            # Try installing specific version; capture failure gracefully
            if sudo apt-get install -y python${PYTHON_XY_VERSION} python${PYTHON_XY_VERSION}-dev python${PYTHON_XY_VERSION}-venv python${PYTHON_XY_VERSION}-pip; then
                echo "Successfully installed Python ${PYTHON_XY_VERSION}."
            else
                echo "Failed to install Python ${PYTHON_XY_VERSION}. Falling back to updating development dependencies..."

                # Update system and fallback to latest Python dev tools
                sudo apt-get update -y
                sudo apt-get install -y python3 python3-dev python3-venv python3-pip
                echo "Installed latest available Python3 development environment."
            fi
        fi

        # Always ensure pip, venv, and dev dependencies are up-to-date
        echo "--> Upgrading pip and development dependencies..."
        python3 -m pip install --upgrade pip setuptools wheel virtualenv || true
        echo "Python development environment refreshed for ${PYTHON_XY_VERSION}."
        echo
    done
fi


######################################
#         Install Java Versions        #
######################################
if [ -n "$JAVA_VERSIONS_STRING" ]; then
    for JAVA_VERSION in $JAVA_VERSIONS_STRING; do
        echo ">>> Processing Java (OpenJDK) ${JAVA_VERSION}..."
        
        # **CHECK 2: Use dpkg to check if the JDK package is already installed.**
        if dpkg -s "openjdk-${JAVA_VERSION}-jdk" &> /dev/null; then
            echo "--> OpenJDK ${JAVA_VERSION} is already installed. Skipping installation."
        else
            echo "--> Installing OpenJDK ${JAVA_VERSION} from APT..."
            sudo apt-get install -y "openjdk-${JAVA_VERSION}-jdk"
        fi
        
        # Find the installation path for this version. This will be overwritten on each loop, 
        # so the last one becomes the default JAVA_HOME.
        LATEST_JAVA_HOME_PATH="/usr/lib/jvm/java-${JAVA_VERSION}-openjdk-amd64"
    done
fi

######################################
#  Update System & User Environments #
######################################
if [ -n "$LATEST_JAVA_HOME_PATH" ] && [ -d "$LATEST_JAVA_HOME_PATH" ]; then
    echo ">>> Setting system-wide JAVA_HOME to the last installed version: ${LATEST_JAVA_HOME_PATH}"
    sudo tee /etc/profile.d/jdk_custom.sh > /dev/null << EOF
export JAVA_HOME=${LATEST_JAVA_HOME_PATH}
export PATH=\$JAVA_HOME/bin:\$PATH
EOF
    sudo chmod +x /etc/profile.d/jdk_custom.sh
fi

######################################
#           Final Verification       #
######################################
echo ">>> Verifying all requested versions are installed..."
all_ok=true

# Verify Python versions
if [ -n "$PYTHON_VERSIONS_STRING" ]; then
    for FULL_PYTHON_VERSION in $PYTHON_VERSIONS_STRING; do
        PYTHON_XY_VERSION=$(echo "$FULL_PYTHON_VERSION" | cut -d. -f1,2)
        if ! command -v "python${PYTHON_XY_VERSION}" &> /dev/null; then
            echo " VERIFICATION FAILED: Python ${PYTHON_XY_VERSION} is not installed."
            all_ok=false
        else
            echo " Verified: Python ${PYTHON_XY_VERSION} is installed."
        fi
    done
fi

# Verify Java versions
if [ -n "$JAVA_VERSIONS_STRING" ]; then
    for JAVA_VERSION in $JAVA_VERSIONS_STRING; do
        if ! dpkg -s "openjdk-${JAVA_VERSION}-jdk" &> /dev/null; then
            echo " VERIFICATION FAILED: OpenJDK ${JAVA_VERSION} is not installed."
            all_ok=false
        else
            echo "Verified: OpenJDK ${JAVA_VERSION} is installed."
        fi
    done
fi

# Final status check
if [ "$all_ok" = false ]; then
    echo "--------------------------------------------------------"
    echo "FATAL: One or more required dependencies were not found after installation. Please check the logs."
    echo "--------------------------------------------------------"
    exit 1
else
    echo "All requested dependencies have been successfully verified."
fi

echo ""
echo "All done! For changes to take effect, users must log out and back in or run 'source ~/.bashrc'."