# 1. Base Image: Amazon Linux 2023 with Python 3.13
# We use the AWS Lambda provided base image for 3.13 to ensure 
# the Lambda Runtime Interface is pre-installed and optimized.
FROM public.ecr.aws/lambda/python:3.13

# 2. System Dependencies
# Why: AL2023 uses 'dnf' again (it was missing in older AL2 images).
# We install GCC and development headers required for PyMuPDF's C-extensions.
RUN dnf update -y && \
    dnf install -y gcc gcc-c++ pkgconfig findutils tar gzip mesa-libGL

# 3. Copy Requirements
# We do this before copying code to maximize Docker layer caching.
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 4. Install Python Dependencies
# We upgrade pip to the latest version to ensure 3.13 compatibility 
# and support for the latest manylinux wheels.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy Application Code
# This moves your 'common' package into the root directory of the Lambda task.
COPY common ${LAMBDA_TASK_ROOT}/common

# 6. Set the Default Handler
# In CDK, we will override this for different Lambda functions:
# - Ingest Worker: common.ingest_worker.handler
# - Link Worker:   common.link_worker.handler
CMD [ "common.ingest_worker.handler" ]