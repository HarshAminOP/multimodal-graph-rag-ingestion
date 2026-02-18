from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    CfnOutput
)
from constructs import Construct
import os

class MultimodalGraphRagIngestionStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        target_region = self.region

        # 1. S3 Bucket (The Landing Zone)
        self.doc_bucket = s3.Bucket(self, "GraphRagDocs",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            event_bridge_enabled=True 
        )

        # 2. Secrets Manager (The Vault)
        self.api_secrets = secretsmanager.Secret(self, "RAGSystemSecrets",
            secret_name="GraphRAG/Production/Secrets",
            removal_policy=RemovalPolicy.DESTROY
        )

        # 3. Docker Image Asset (Builds Python 3.13 Image)
        rag_image_code = _lambda.DockerImageCode.from_image_asset(".", directory=".", platform=_lambda.Platform.LINUX_AMD64)

        # 4. Workers
        self.ingest_worker = _lambda.DockerImageFunction(self, "IngestWorker",
            code=rag_image_code,
            command=["common.ingest_worker.handler"],
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "SECRET_ARN": self.api_secrets.secret_arn,
                "S3_BUCKET_NAME": self.doc_bucket.bucket_name,
                "UPLOAD_TO_S3": "true",
                "AWS_REGION": target_region
            }
        )

        self.link_worker = _lambda.DockerImageFunction(self, "LinkWorker",
            code=rag_image_code,
            command=["common.link_worker.handler"],
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "SECRET_ARN": self.api_secrets.secret_arn,
                "AWS_REGION": target_region
            }
        )

        # Permissions
        self.api_secrets.grant_read(self.ingest_worker)
        self.api_secrets.grant_read(self.link_worker)
        self.doc_bucket.grant_read_write(self.ingest_worker)

        # 5. State Machine Orchestration
        log_group = logs.LogGroup(self, "RAGWorkflowLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Load ASL and swap placeholder ARNs
        asl_file_path = os.path.join(os.getcwd(), "statemachine.asl.json")
        with open(asl_file_path, "r") as f:
            asl_string = f.read()

        asl_final = asl_string.replace("${IngestFunctionArn}", self.ingest_worker.function_arn) \
                              .replace("${LinkFunctionArn}", self.link_worker.function_arn)

        self.state_machine = sfn.StateMachine(self, "RAGWorkflow",
            definition_body=sfn.DefinitionBody.from_string(asl_final),
            logs=sfn.LogOptions(
                destination=log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True
            ),
            timeout=Duration.minutes(20)
        )

        # 6. Lifecycle Trigger (Create/Modify/Delete)
        s3_event_rule = events.Rule(self, "S3LifecycleRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created", "Object Deleted"],
                detail={
                    "bucket": {"name": [self.doc_bucket.bucket_name]},
                    "object": {"key": [{"suffix": ".pdf"}]}
                }
            )
        )
        s3_event_rule.add_target(targets.SfnStateMachine(self.state_machine))

        # --- ARNs & RESOURCE OUTPUTS ---
        CfnOutput(self, "StackArn", value=self.stack_id)
        CfnOutput(self, "IngestWorkerArn", value=self.ingest_worker.function_arn)
        CfnOutput(self, "LinkWorkerArn", value=self.link_worker.function_arn)
        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)
        CfnOutput(self, "BucketName", value=self.doc_bucket.bucket_name)
        CfnOutput(self, "SecretArn", value=self.api_secrets.secret_arn)