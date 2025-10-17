node {
    properties([
        parameters([
            choice(name: 'TARGET_ENV', choices: ['Dev', 'QA', 'Prod'], description: 'Select the target environment for deployment.'),
            string(name: 'DEPLOY_VERSION', defaultValue: '1.0.0', description: 'Enter the version to deploy (e.g., 1.2.3).'),

            booleanParam(name: 'DEPLOY_ZOOKEEPER', defaultValue: false, description: 'Deploy Zookeeper?'),
            booleanParam(name: 'DEPLOY_KAFKA', defaultValue: false, description: 'Deploy Kafka?'),
            booleanParam(name: 'DEPLOY_DORIS_FE', defaultValue: false, description: 'Deploy Doris FE?'),
            booleanParam(name: 'DEPLOY_DORIS_BE', defaultValue: false, description: 'Deploy Doris BE?'),
            booleanParam(name: 'DEPLOY_NODE_EXPORTER', defaultValue: false, description: 'Deploy Node Exporter?'),
            booleanParam(name: 'DEPLOY_KAFKA_EXPORTER', defaultValue: false, description: 'Deploy Kafka Exporter?'),
            booleanParam(name: 'DEPLOY_PROMETHEUS', defaultValue: false, description: 'Deploy Prometheus?'),
            booleanParam(name: 'DEPLOY_GRAFANA', defaultValue: false, description: 'Deploy Grafana?'),
            booleanParam(name: 'DEPLOY_HEALTH_REPORTS', defaultValue: false, description: 'Deploy Health Reports?'),
            booleanParam(name: 'DEPLOY_RECON', defaultValue: false, description: 'Deploy Recon?'),
            booleanParam(name: 'DEPLOY_JOBS', defaultValue: false, description: 'Deploy Jobs?'),
            booleanParam(name: 'DEPLOY_API', defaultValue: false, description: 'Deploy API?'),
            booleanParam(name: 'DEPLOY_NGINX', defaultValue: false, description: 'Deploy Nginx?')
        ])
    ])

    try {
        stage('Initialization') {
            echo "Pipeline started for environment: ${params.TARGET_ENV}"
            echo "Deploy App One: ${params.DEPLOY_APP_ONE}, Deploy App Two: ${params.DEPLOY_APP_TWO}"
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