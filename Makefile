# D5 commands. Override PYTHON or ARTIFACT_ZIP when your local paths differ.
PYTHON ?= python
ARTIFACT_ZIP ?= .scratch/vnlegal-demo-v1.zip
ARTIFACT_SHA256 ?= 059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096

.PHONY: fetch-artifacts up smoke demo-local

fetch-artifacts:
	"$(PYTHON)" -X utf8 scripts/fetch_artifacts.py --zip "$(ARTIFACT_ZIP)" --sha256 "$(ARTIFACT_SHA256)" --output-dir ./artifacts

up:
	docker compose up --build

smoke:
	"$(PYTHON)" -X utf8 scripts/smoke_demo.py

ifeq ($(OS),Windows_NT)
demo-local:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_demo.ps1
else
demo-local:
	bash scripts/run_demo.sh
endif
