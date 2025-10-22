node {
    properties([
        parameters([
            booleanParam(name: 'SMS', defaultValue: false),
            booleanParam(name: 'RCS', defaultValue: false),
            booleanParam(name: 'Whatsapp', defaultValue: false),

            choice(name: 'TARGET_ENV', choices: ['Dev', 'QA', 'Prod', 'SBI Prod', 'SMPP DR', 'Functional Lab'], description: 'Select the target environment for deployment.'),

            string(name: 'DEPLOY_VERSION', defaultValue: '1.0.0', description: 'Enter the version to deploy (e.g., 1.2.3).'),

            booleanParam(name: 'Select_All', defaultValue: false, description: 'Select this to deploy all application services (Zookeeper to Nginx).'),

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
                                [path: 'Jenkins/deployment-pipeline/Releases/']
                            ]]
                        ]
                    ])
                    sh 'git config --global --unset lfs.https://github.com/1xtel/ODP.git.header'
                }
            }

            echo "Copying folders to the workspace root..."
            sh "cp -r temp_private_repo/Jenkins/deployment-pipeline/Releases ./"
            
            echo "Successfully loaded Script and Releases directories."
        }

        stage('Gather Configuration Files') {
            echo "Fetching configuration files from ODP-configs repo..."
            dir('temp_config_repo') {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    userRemoteConfigs: [[url: 'https://github.com/onex-saksham/ODP-configs.git']]
                ])
            }

            echo "Copying config files to the Script directory..."
            sh "cp temp_config_repo/passwords.json Script/"
            sh "cp temp_config_repo/smtp_config.json Script/"

            echo "Successfully loaded configuration files."
        }

       stage('Prepare and Update Config') {
            echo "Copying master config file for ${params.TARGET_ENV} into the Script/ directory..."
            sh "cp configs/${params.TARGET_ENV.toLowerCase()}/initialization_deployment_config.json Script/"
            echo "Successfully loaded master configuration file."

            script {
                def masterConfigFile = 'Script/initialization_deployment_config.json'
                def developerConfigFile = 'temp_config_repo/initialization_deployment_config_developers.json'
                
                echo "Reading master configuration from ${masterConfigFile}..."
                def config = readJSON file: masterConfigFile

                echo "Reading developer override configuration from ${developerConfigFile}..."
                def developerConfig = readJSON file: developerConfigFile

                echo "Merging developer overrides into master configuration..."
                config.putAll(developerConfig)

                echo "Updating merged configuration with build parameters..."
                
                // config.base_user = "jenkins"

                if (!config.releases) { config.releases = [:] }
                if (!config.deploy) { config.deploy = [:] }
                
                config.releases.new_version = params.DEPLOY_VERSION
                
                config.deploy_sms = params.SMS.toString()
                config.deploy_rcs = params.RCS.toString()
                config.deploy_whatsapp = params.Whatsapp.toString()

                def services = [
                    'ZOOKEEPER', 'KAFKA', 'NIFI', 'NIFI_REGISTRY', 'DORIS_FE', 'DORIS_BE', 
                    'CONNECT_FE_BE', 'NODE_EXPORTER', 'KAFKA_EXPORTER', 'PROMETHEUS', 
                    'GRAFANA','HEALTH_REPORTS', 'RECON', 'JOBS', 'API', 'NGINX'
                ]
                
                if (params.Select_All) {
                    echo "Select_All is selected. Overriding individual service selections."
                }

                services.each { serviceName ->
                    def jsonKey = serviceName.toLowerCase().replace(' ', '_')
                    def paramValue = params.Select_All ? true : params[serviceName]
                    
                    echo " - Setting service '${jsonKey}' to '${paramValue}'"
                    config.deploy[jsonKey] = paramValue.toString()
                }
                
                
                echo "Writing final updated configuration back to ${masterConfigFile}..."
                writeJSON file: masterConfigFile, json: config, pretty: 4
                
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
            echo "Preparing SSH key and Python environment..."
            
            // Use withCredentials to load the key from Jenkins into a temporary file
            withCredentials([sshUserPrivateKey(credentialsId: 'server-ssh-key', keyFileVariable: 'SSH_KEY_FILE')]) {
                try {
                    dir('Script') {
                        sh '''
                            echo "Setting up temporary SSH key..."
                            mkdir -p /home/jenkins/.ssh
                            cp "$SSH_KEY_FILE" /home/jenkins/.ssh/id_rsa
                            chmod 600 /home/jenkins/.ssh/id_rsa
                            
                            echo "Creating Python virtual environment..."
                            python3 -m venv venv

                            echo "Installing dependencies..."
                            venv/bin/pip install -r requirements.txt
                            
                            echo "Running the deployment script..."
                            export LOG_TO_CONSOLE=true
                            venv/bin/python3 deployment.py
                        '''
                    }
                } finally {
                    echo "Cleaning up temporary SSH key..."
                    sh 'rm -rf /home/jenkins/.ssh'
                }
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