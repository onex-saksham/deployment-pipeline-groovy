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

        stage('Parameter Pulling from Git') {
            echo "SUCCESS: This stage would pull configs for ${params.TARGET_ENV}."
        }

        stage('Parameter Validation') {
             echo "SUCCESS: This stage would pause for manual validation in Production."
        }

        stage('Test Cases (Planned)') {
            echo "SUCCESS: Placeholder stage for automated tests."
        }

        stage('Deployment Execution') {
            echo "SUCCESS: This stage would execute the deployment.py script."
        }

        stage('Validation (Planned)') {
            echo "SUCCESS: Placeholder stage for post-deployment validation."
        }

    } catch (e) {
        echo "An error occurred during the pipeline execution: ${e.getMessage()}"
        currentBuild.result = 'FAILURE'
    } finally {
        stage('Cleanup') {
            echo "Cleaning up workspace..."
            cleanWs()
        }
    }
}