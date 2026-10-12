-- Web onboarding: an account is registered first (scan_enabled = false), the
-- customer creates the IAM role, and a successful AssumeRole check from the
-- dashboard stamps verified_at and enables scheduled scans.
ALTER TABLE aws_accounts ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
