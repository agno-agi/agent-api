from os import getenv

from agno.aws.app.fastapi import FastApi
from agno.aws.resources import AwsResources
from agno.aws.resource.ecs import EcsCluster
from agno.aws.resource.ec2 import SecurityGroup, InboundRule
from agno.aws.resource.rds import DbInstance, DbSubnetGroup
from agno.aws.resource.reference import AwsReference
from agno.aws.resource.s3 import S3Bucket
from agno.aws.resource.secret import SecretsManager
from agno.docker.resources import DockerResources
from agno.docker.resource.image import DockerImage

from workspace.settings import (
    BUILD_IMAGES,
    IMAGE_REPO,
    PRD_ENV,
    PRD_KEY,
    WS_NAME,
    WS_ROOT,
    SUBNET_IDS,
    AWS_AZ1,
)

#
# -*- Resources for the Production Environment
#
# Skip resource deletion when running `phi ws down` (set to True after initial deployment)
skip_delete: bool = False
# Save resource outputs to workspace/outputs
save_output: bool = True

# -*- Production image
prd_image = DockerImage(
    name=f"{IMAGE_REPO}/{WS_NAME}",
    tag=PRD_ENV,
    enabled=BUILD_IMAGES,
    path=str(WS_ROOT),
    platforms=["linux/amd64", "linux/arm64"],
    push_image=True,
)

# -*- S3 bucket for production data (set enabled=True when needed)
prd_bucket = S3Bucket(
    name=f"{PRD_KEY}-data",
    enabled=False,
    acl="private",
    skip_delete=skip_delete,
    save_output=save_output,
)

# -*- Secrets for production application
prd_secret = SecretsManager(
    name=f"{PRD_KEY}-api-secret",
    enabled=True,
    group="api",
    # Create secret from workspace/secrets/prd_api_secrets.yml
    secret_files=[WS_ROOT.joinpath("workspace/secrets/prd_api_secrets.yml")],
    skip_delete=skip_delete,
    save_output=save_output,
)
# -*- Secrets for production database
prd_db_secret = SecretsManager(
    name=f"{PRD_KEY}-db-secret",
    enabled=True,
    group="db",
    # Create secret from workspace/secrets/prd_db_secrets.yml
    secret_files=[WS_ROOT.joinpath("workspace/secrets/prd_db_secrets.yml")],
    skip_delete=skip_delete,
    save_output=save_output,
)

# -*- Security Group for the load balancer
prd_lb_sg = SecurityGroup(
    name=f"{PRD_KEY}-lb-sg",
    enabled=True,
    group="api",
    description="Security group for the load balancer",
    inbound_rules=[
        InboundRule(
            description="Allow HTTP traffic from the internet",
            port=80,
            cidr_ip="0.0.0.0/0",
        ),
        InboundRule(
            description="Allow HTTPS traffic from the internet",
            port=443,
            cidr_ip="0.0.0.0/0",
        ),
    ],
    skip_delete=skip_delete,
    save_output=save_output,
)
# -*- Security Group for the application
prd_sg = SecurityGroup(
    name=f"{PRD_KEY}-api-sg",
    enabled=True,
    group="api",
    description="Security group for the production application",
    inbound_rules=[
        InboundRule(
            description="Allow traffic from LB to the FastAPI server",
            port=8000,
            security_group_id=AwsReference(prd_lb_sg.get_security_group_id),
        ),
        InboundRule(
            description="Allow traffic from LB to the Streamlit app",
            port=8501,
            security_group_id=AwsReference(prd_lb_sg.get_security_group_id),
        ),
    ],
    depends_on=[prd_lb_sg],
    skip_delete=skip_delete,
    save_output=save_output,
)
# -*- Security Group for the database
prd_db_port = 5432
prd_db_sg = SecurityGroup(
    name=f"{PRD_KEY}-db-sg",
    enabled=True,
    group="db",
    description="Security group for the production database",
    inbound_rules=[
        InboundRule(
            description="Allow traffic from apps to the database",
            port=prd_db_port,
            security_group_id=AwsReference(prd_sg.get_security_group_id),
        ),
    ],
    depends_on=[prd_sg],
    skip_delete=skip_delete,
    save_output=save_output,
)

# -*- RDS Database Subnet Group
prd_db_subnet_group = DbSubnetGroup(
    name=f"{PRD_KEY}-db-sg",
    enabled=True,
    group="db",
    subnet_ids=SUBNET_IDS,
    skip_delete=skip_delete,
    save_output=save_output,
)

# -*- RDS Database Instance
prd_db = DbInstance(
    name=f"{PRD_KEY}-db",
    enabled=True,
    group="db",
    db_name="ai",
    port=prd_db_port,
    engine="postgres",
    engine_version="16.4",
    allocated_storage=64,
    # NOTE: For production, use a larger instance type.
    # Last checked price: ~$25 per month
    db_instance_class="db.t4g.small",
    db_security_groups=[prd_db_sg],
    db_subnet_group=prd_db_subnet_group,
    availability_zone=AWS_AZ1,
    publicly_accessible=False,
    enable_performance_insights=True,
    aws_secret=prd_db_secret,
    skip_delete=skip_delete,
    save_output=save_output,
    # Do not wait for the db to be deleted
    wait_for_delete=False,
)

# -*- ECS cluster
prd_ecs_cluster = EcsCluster(
    name=f"{PRD_KEY}-cluster",
    ecs_cluster_name=PRD_KEY,
    capacity_providers=["FARGATE"],
    skip_delete=skip_delete,
    save_output=save_output,
)

# -*- Build container environment
container_env = {
    "RUNTIME_ENV": "prd",
    # Get the OpenAI API key from the local environment
    "OPENAI_API_KEY": getenv("OPENAI_API_KEY"),
    "PHI_MONITORING": "True",
    "PHI_API_KEY": getenv("PHI_API_KEY"),
    # Database configuration
    "DB_HOST": AwsReference(prd_db.get_db_endpoint),
    "DB_PORT": AwsReference(prd_db.get_db_port),
    "DB_USER": AwsReference(prd_db.get_master_username),
    "DB_PASS": AwsReference(prd_db.get_master_user_password),
    "DB_DATABASE": AwsReference(prd_db.get_db_name),
    # Wait for database to be available before starting the application
    "WAIT_FOR_DB": True,
    # Migrate database on startup using alembic
    # "MIGRATE_DB": ws_settings.prd_db_enabled,
}

# -*- FastApi running on ECS
prd_fastapi = FastApi(
    name=f"{PRD_KEY}-api",
    enabled=True,
    group="api",
    image=prd_image,
    command="uvicorn api.main:app --workers 2",
    port_number=8000,
    ecs_task_cpu="1024",
    ecs_task_memory="2048",
    ecs_service_count=1,
    ecs_cluster=prd_ecs_cluster,
    aws_secrets=[prd_secret],
    subnets=SUBNET_IDS,
    security_groups=[prd_sg],
    # To enable HTTPS, create an ACM certificate and add the ARN below:
    # load_balancer_enable_https=True,
    # load_balancer_certificate_arn="LOAD_BALANCER_CERTIFICATE_ARN",
    load_balancer_security_groups=[prd_lb_sg],
    create_load_balancer=True,
    health_check_path="/v1/health",
    env_vars=container_env,
    use_cache=True,
    skip_delete=skip_delete,
    save_output=save_output,
    # Do not wait for the service to stabilize
    wait_for_create=False,
    # Do not wait for the service to be deleted
    wait_for_delete=False,
)

# -*- Production DockerResources
prd_docker_resources = DockerResources(
    env=PRD_ENV,
    network=WS_NAME,
    resources=[prd_image],
)

# -*- Production AwsResources
prd_aws_config = AwsResources(
    env=PRD_ENV,
    apps=[prd_fastapi],
    resources=(
        prd_lb_sg,
        prd_sg,
        prd_db_sg,
        prd_secret,
        prd_db_secret,
        prd_db_subnet_group,
        prd_db,
        prd_ecs_cluster,
        prd_bucket,
    ),
)
