# Drop-a-receipt verifier (integrity grade)

Static browser page for **unsigned PCAW v1** integrity checks.

Live when GitHub Pages is enabled for this folder:
`https://coystan.github.io/palari-company-os/`

## What it checks

1. Well-formed UTF-8 / I-JSON (no floats)
2. PCAW v1 in-toto statement envelope
3. Required `security_limitations` non-claims
4. Work-state subject digest binds `predicate.governance_case`
5. Optional artifact SHA-256 digests when files are supplied

## What it does **not** check

- Signatures, keys, trusted time, or authenticated actors (PCAW v1 is unsigned)
- Full governance properties (scope, review independence, quorum, acceptance
  currency) — use the CLI:
  `palari proof verify statement.json --subject-root DIR`
- Not WRP-10 from the Blueprint (signed drop-a-receipt after DSSE / WebCrypto work)

## Local preview

```bash
python3 -m http.server 8765 --directory verify
# open http://127.0.0.1:8765/
```

## Tests

```bash
node verify/test_integrity.mjs
python3 -S -m unittest tests.test_verify_page -v
```
