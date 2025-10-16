// Groovy Scripted Pipeline

node {
    // Define properties, including build parameters
    properties([
        parameters([
            choice(name: 'TARGET_ENV', choices: ['Dev', 'QA', 'Prod'], description: 'Select the target environment for deployment.'),
            booleanParam(name: 'DEPLOY_APP_ONE', defaultValue: true, description: 'Deploy Application One?'),
            booleanParam(name: 'DEPLOY_APP_TWO', defaultValue: false, description: 'Deploy Application Two?')
        ])
    ])

    // Use a try-catch-finally block for robust error handling and cleanup
    try {
        stage('Initialization & Checkout') {
            echo "Starting deployment process for environment: ${params.TARGET_ENV}"
            echo "Deploy App One: ${params.DEPLOY_APP_ONE}"
            echo "Deploy App Two: ${params.DEPLOY_APP_TWO}"

            // Checkout the source code from your Git repository
            // This assumes your Jenkins job is configured to pull from the correct repo
            checkout scm
        }

        stage('Pulling Configs from Git') {
            echo "Fetching configuration for ${params.TARGET_ENV}..."
            // Assuming your configs are in a folder like /jenkins/configs/<env_name>/
            // This command copies the correct JSON files to the workspace root
            // The pipeline will fail if the config directory doesn't exist
            sh "cp jenkins/configs/${params.TARGET_ENV.toLowerCase()}/*.json ."
            echo "Configuration files pulled successfully."
        }

        stage('Manual Approval for Production') {
            // Only trigger this stage if the target environment is 'Prod'
            if (params.TARGET_ENV == 'Prod') {
                timeout(time: 5, unit: 'MINUTES') {
                    // Pauses the pipeline and waits for a user to click "Proceed" or "Abort"
                    input message: "Proceed with PRODUCTION deployment?", ok: "Yes, Deploy to Production"
                }
            } else {
                echo "Skipping manual approval for non-production environment."
            }
        }

        stage('Test Cases (Planned)') {
            echo "This is a placeholder for future automated test cases."
            // When ready, you can add your test script execution here.
            // Example: sh './run_tests.sh'
        }

        stage('Deployment Execution') {
            echo "Executing the deployment script..."
            // Construct the command for the Python script
            // You can pass Jenkins parameters to your Python script as command-line arguments
            def deployCommand = "python3 deployment.py --environment ${params.TARGET_ENV}"
            if (params.DEPLOY_APP_ONE) {
                deployCommand += " --app-one"
            }
            if (params.DEPLOY_APP_TWO) {
                deployCommand += " --app-two"
            }
            
            // Execute the script. The `sh` step will fail the build if the script returns a non-zero exit code.
            sh deployCommand
        }

        stage('Validation (Planned)') {
            echo "This is a placeholder for post-deployment validation."
            // When ready, you can add health checks or version checks here.
            // Example: sh './validate_deployment.sh'
        }

    } catch (e) {
        // This block catches any errors that occurred in the stages above
        echo "An error occurred: ${e.getMessage()}"
        currentBuild.result = 'FAILURE'
        throw e // Re-throw the exception to ensure the pipeline is marked as failed
    } finally {
        // This block will always execute, whether the build succeeds or fails
        stage('Cleanup') {
            echo "Cleaning up workspace..."
            // Add any cleanup steps here, like deleting temporary files
            cleanWs()
        }
    }
}