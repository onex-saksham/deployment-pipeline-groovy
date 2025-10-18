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
            booleanParam(name: 'NIFI', defaultValue: false),
            booleanParam(name: 'NIFI_REGISTRY', defaultValue: false),
            booleanParam(name: 'DORIS_FE', defaultValue: false),
            booleanParam(name: 'DORIS_BE', defaultValue: false),
            booleanParam(name: 'CONNECT_FE_BE', defaultValue: false),
            booleanParam(name: 'NODE_EXPORTER', defaultValue: false),
            booleanParam(name: 'KAFKA_EXPORTER', defaultValue: false),
            booleanParam(name: 'PROMETHEUS', defaultValue: false),
            booleanParam(name: 'GRAFANA', defaultValue: false),
            booleanParam(name: 'HEALTH_REPORTS', defaultValue: false),
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
            echo "Fetching Script and Releases folders from private repo..."
            dir('temp_private_repo') {
                withCredentials([usernamePassword(credentialsId: 'private-github-token', passwordVariable: 'GITHUB_TOKEN', usernameVariable: 'GITHUB_USER')]) {
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
                    sh 'git config --global --unset lfs.https://github.com/1xtel/ODP.git.header'
                }
            }

            echo "Copying folders to the workspace root..."
            sh "cp -r temp_private_repo/Jenkins/deployment-pipeline/Script ./"
            sh "cp -r temp_private_repo/Jenkins/deployment-pipeline/Releases ./"
            
            echo "Successfully loaded Script and Releases directories."
        }

        stage('Prepare and Update Config') {
            // 'steps' block has been removed from here
            echo "Copying config files for ${params.TARGET_ENV} into the Script/ directory..."
            sh "cp configs/${params.TARGET_ENV.toLowerCase()}/*.json Script/"
            echo "Successfully loaded configuration files."

            script {
                def configFile = 'Script/initialization_deployment_config.json'
                
                echo "Reading configuration from ${configFile}..."
                def config = readJSON file: configFile

                echo "Updating configuration with build parameters..."

                // Ensure the parent objects exist before setting properties
                if (!config.releases) { config.releases = [:] }
                if (!config.deploy) { config.deploy = [:] }
                
                // 1. Update the deployment version
                config.releases.new_version = params.DEPLOY_VERSION

                // 2. Update the top-level channel flags
                config.deploy_sms = params.SMS
                config.deploy_rcs = params.RCS
                config.deploy_whatsapp = params.Whatsapp

                // 3. Update all the service flags inside the 'deploy' object
                def services = [
                    'ZOOKEEPER', 'KAFKA', 'NIFI', 'NIFI_REGISTRY', 'DORIS_FE', 'DORIS_BE', 
                    'CONNECT_FE_BE', 'NODE_EXPORTER', 'KAFKA_EXPORTER', 'PROMETHEUS', 
                    'GRAFANA','HEALTH_REPORTS', 'RECON', 'JOBS', 'API', 'NGINX'
                ]

                services.each { serviceName ->
                    // Convert parameter name to a JSON-friendly key
                    def jsonKey = serviceName.toLowerCase().replace(' ', '_')
                    def paramValue = params[serviceName]
                    
                    echo " - Setting service '${jsonKey}' to '${paramValue}'"
                    config.deploy[jsonKey] = paramValue
                }
                
                echo "Writing updated configuration back to ${configFile}..."
                writeJSON file: configFile, json: config, pretty: 4
                
                echo "Successfully updated initialization_deployment_config.json."
            }
        }
        
        stage('Parameter Validation') {
            echo "Displaying updated configuration for validation:"
            
            sh 'cat Script/initialization_deployment_config.json'
            
            input(
                message: 'Please review the deployment configuration above. Do you want to proceed?',
                ok: 'Yes, Proceed with Deployment' 
            )
            
            echo "Validation approved. Continuing to the next stage..."
        }

        stage('Test Cases (Planned)') {
            echo "SUCCESS: Placeholder stage for automated tests."
        }

        stage('Deployment Execution') {
            echo "Preparing Python environment and running deployment script..."
            dir('Script') {
                sh '''
                    # ... (Python check and venv setup are the same) ...

                    echo "Installing dependencies from requirements.txt..."
                    venv/bin/pip install -r requirements.txt
                    
                    # --- CORRECTED SCRIPT EXECUTION ---
                    echo "Running the deployment script using the venv python..."
                    
                    # This is the correct way to run the script.
                    # It directly uses the python from the virtual environment.
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
    } 
    // finally {
    //     stage('Cleanup') {
    //         echo "Cleaning up workspace..."
    //         cleanWs()
    //     }
    // }
}