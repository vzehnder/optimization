ARG PYTHON_IMAGE=python@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
FROM ${PYTHON_IMAGE}
COPY entry.py /runtime/entry.py
USER 65532:65532
WORKDIR /runtime
ENTRYPOINT ["python", "-I", "-B", "/runtime/entry.py"]
