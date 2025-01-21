from os import getenv

from agno.docker.app.fastapi import FastApi
from agno.docker.app.postgres import PgVectorDb
from agno.docker.resource.image import DockerImage
from agno.docker.resources import DockerResources

from workspace.settings import BUILD_IMAGES, DEV_ENV, DEV_KEY, IMAGE_REPO, WS_NAME, WS_ROOT

#
# -*- Resources for the Development Environment
#

# -*- Dev image
dev_image = DockerImage(
    name=f"{IMAGE_REPO}/{WS_NAME}",
    tag=DEV_ENV,
    enabled=BUILD_IMAGES,
    path=str(WS_ROOT),
    push_image=False,
)

# -*- Dev database running on port 5432:5432
dev_db = PgVectorDb(
    name=f"{WS_NAME}-db",
    enabled=True,
    pg_user="ai",
    pg_password="ai",
    pg_database="ai",
    # Connect to this db on port 5432
    host_port=5432,
)

# -*- Build container environment
container_env = {
    "RUNTIME_ENV": "dev",
    # Get the OpenAI API key from the local environment
    "OPENAI_API_KEY": getenv("OPENAI_API_KEY"),
    "PHI_MONITORING": "True",
    "PHI_API_KEY": getenv("PHI_API_KEY"),
    # Database configuration
    "DB_HOST": dev_db.get_db_host(),
    "DB_PORT": dev_db.get_db_port(),
    "DB_USER": dev_db.get_db_user(),
    "DB_PASS": dev_db.get_db_password(),
    "DB_DATABASE": dev_db.get_db_database(),
    # Wait for database to be available before starting the application
    "WAIT_FOR_DB": True,
    # Migrate database on startup using alembic
    # "MIGRATE_DB": True,
}

# -*- FastApi running on port 8000:8000
dev_fastapi = FastApi(
    name=DEV_KEY,
    enabled=True,
    image=dev_image,
    command="uvicorn api.main:app --reload",
    port_number=8000,
    debug_mode=True,
    mount_workspace=True,
    env_vars=container_env,
    use_cache=True,
    # Read secrets from secrets/dev_api_secrets.yml
    secrets_file=WS_ROOT.joinpath("workspace/secrets/dev_api_secrets.yml"),
    depends_on=[dev_db],
)

# -*- Dev DockerResources
dev_docker_resources = DockerResources(
    env=DEV_ENV,
    network=WS_NAME,
    apps=[dev_db, dev_fastapi],
)
