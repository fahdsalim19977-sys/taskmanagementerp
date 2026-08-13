# P0 Security Migration

This branch is reserved for security and core-data integrity fixes. Existing password hashes must be migrated from legacy SHA-256 to a password-specific hashing algorithm during successful login. Default credentials and production secrets must not be stored in source code.
