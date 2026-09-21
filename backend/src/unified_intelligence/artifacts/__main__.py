import argparse

from unified_intelligence.artifacts.manager import ArtifactManager
from unified_intelligence.artifacts.manifest import ArtifactManifest
from unified_intelligence.core.config import PROJECT_ROOT, get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage external project artifacts.")
    parser.add_argument("command", choices=("verify", "sync"))
    arguments = parser.parse_args()
    settings = get_settings()
    manager = ArtifactManager(PROJECT_ROOT, ArtifactManifest.load(settings.artifact_manifest))
    if arguments.command == "sync":
        if not settings.artifact_base_url:
            parser.error("UID_ARTIFACT_BASE_URL is required for sync.")
        statuses = manager.sync(settings.artifact_base_url)
    else:
        statuses = manager.verify()
    for status in statuses:
        print(f"{'OK' if status.valid else 'ERROR'} {status.name}: {status.reason}")
    return 0 if all(status.valid for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
