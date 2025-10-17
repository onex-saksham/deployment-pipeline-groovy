node {
    properties([
        parameters([
            booleanParam(name: 'SMS', defaultValue: false),
            booleanParam(name: 'RCS', defaultValue: false),
            booleanParam(name: 'Whatsapp', defaultValue: false),

            choice(name: 'TARGET_ENV', choices: ['Dev', 'QA', 'Prod', 'SBI Prod', 'SMPP DR', 'Functional Lab'], description: 'Select the target environment for deployment.'),

            string(name: 'DEPLOY_VERSION', defaultValue: '1.0.0', description: 'Enter the version to deploy (e.g., 1.2.3).'),

            booleanParam(name: 'ZOOKEEPER', defaultValue: false),
            booleanParam(name: 'KAFKA', defaultValue: false),
            booleanParam(name: 'DORIS_FE', defaultValue: false),
            booleanParam(name: 'DORIS_BE', defaultValue: false),
            booleanParam(name: 'NODE_EXPORTER', defaultValue: false),
            booleanParam(name: 'KAFKA_EXPORTER', defaultValue: false),
            booleanParam(name: 'PROMETHEUS', defaultValue: false),
            booleanParam(name: 'GRAFANA', defaultValue: false),
            booleanParam(name: 'HEALTH REPORTS', defaultValue: false),
            booleanParam(name: 'RECON', defaultValue: false),
            booleanParam(name: 'JOBS', defaultValue: false),
            booleanParam(name: 'API', defaultValue: false),
            booleanParam(name: 'NGINX', defaultValue: false)
        ])
    ])

    try {
        stage('Initialization') {
            echo "Pipeline started for environment: ${params.TARGET_ENV}"
            checkout scm
        }

        stage('Gather Script and Releases') {
            // 'steps' block is removed from here
            echo "Fetching Script and Releases folders from private repo..."
            dir('temp_private_repo') {
                withCredentials([usernamePassword(credentialsId: 'private-github-token', passwordVariable: 'GITHUB_TOKEN')]) {                    // Manually configure Git LFS to use the token
                    sh 'git config --global lfs.https://github.com/1xtel/ODP.git.header "Authorization: token ${GITHUB_TOKEN}"'

                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: '*/main']],
                        userRemoteConfigs: [[
                            url: 'https://github.com/1xtel/ODP.git',
                            credentialsId: 'private-github-token'
                        ]],
                        extensions: [
                            [$class: 'GitLFSPull'],
                            [$class: 'SparseCheckoutPaths', sparseCheckoutPaths: [
                                [path: 'Jenkins/deployment-pipeline/Script/'],
                                [path: 'Jenkins/deployment-pipeline/Releases/']
                            ]]
                        ]
                    ])

                    // Clean up the git config to remove the token
                    sh 'git config --global --unset lfs.https://github.com/1xtel/ODP.git.header'
                }
            }

            echo "Copying folders to the workspace root..."
            sh "cp -r temp_private_repo/Jenkins/deployment-pipeline/Script ./"
            sh "cp -r temp_private_repo/Jenkins/deployment-pipeline/Releases ./"
            
            echo "Successfully loaded Script and Releases directories."
        }

        stage('Parameter Pulling from Git') {
            echo "Copying config files for ${params.TARGET_ENV} into the Script/ directory..."
            sh "cp configs/${params.TARGET_ENV.toLowerCase()}/*.json Script/"
            echo "Successfully loaded initialization_deployment_config.json and passwords.json."
        }

        stage('Parameter Validation') {
             echo "SUCCESS: This stage would pause for manual validation in Production."
        }

        stage('Test Cases (Planned)') {
            echo "SUCCESS: Placeholder stage for automated tests."
        }

        stage('Deployment Execution') {
            echo "Preparing Python environment and running deployment script..."
            dir('Script') {
                sh '''
                    # STEP 1: Check for Python3 and install if it's missing
                    if ! command -v python3 &> /dev/null
                    then
                        echo "Python3 not found. This pipeline assumes it is pre-installed on the agent."
                    else
                        echo "Python3 is already installed."
                    fi

                    # STEP 2: Create virtual environment and install dependencies
                    echo "Creating Python virtual environment..."
                    python3 -m venv venv

                    if [ ! -f requirements.txt ]; then
                        echo "requirements.txt not found. Skipping dependency installation."
                    else
                        echo "Installing dependencies from requirements.txt..."
                        venv/bin/pip install -r requirements.txt
                    fi
                    
                    # STEP 3: Run the deployment script
                    echo "Running the deployment script..."
                    venv/bin/python3 deployment.py
                '''
            }
        }

        stage('Validation (Planned)') {
            echo "SUCCESS: Placeholder stage for post-deployment validation."
        }

    } catch (e) {
        echo "An error occurred during the pipeline execution: ${e.getMessage()}"
        currentBuild.result = 'FAILURE'
        error("Pipeline failed")
    } finally {
        stage('Cleanup') {
            echo "Cleaning up workspace..."
            cleanWs()
        }
    }
}