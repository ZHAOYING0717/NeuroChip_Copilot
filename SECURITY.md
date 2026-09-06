# Security

## Supported version

The latest repository version is supported for security fixes.

## Reporting

Report a suspected vulnerability privately through the repository owner's contact channel before public disclosure. Do not attach private datasets, credentials, or sensitive recordings to a public issue.

## Model artifacts

Joblib model files are Python pickle artifacts and can execute code during loading. The application loads only the checked-in files under `models/`. Never replace them with artifacts from an untrusted source.

## Uploaded files

The local dashboard writes uploaded files under `artifacts/uploads/` using a content hash and sanitized basename. Deployments should use an isolated container, restrict filesystem permissions, set upload-size limits, and periodically rotate upload storage according to laboratory policy.

## Data scope

The included public data contain no personal or clinical records. Do not upload protected health information or unauthorized sensitive data to a public deployment.
