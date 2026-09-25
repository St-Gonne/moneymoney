"""NSDL e-CAS adapter with fail-closed coverage and redaction semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from collections import Counter, defaultdict
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Optional

import casparser
import casparser_isin
from casparser.parsers import nsdl as casparser_nsdl
from casparser.parsers import pageobj as casparser_pageobj
from casparser.types import DematAccount, DematOwner, MutualFund, NSDLCASData
import pikepdf
import pypdfium2

from ..models.nsdl_snapshot import (
    NsdlAccount,
    NsdlCoverage,
    NsdlHolding,
    NsdlSnapshotError,
    NsdlSnapshotV1,
    canonical_decimal,
    opaque_id,
    totals_from_holdings,
)


PARSER_VERSION = "casparser-1.4.0+nsdl-adapter-3-source-repair"
_SECTION_TYPES = frozenset({"DEMAT", "MUTUAL_FUND", "NPS"})
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_PLACEHOLDER_NAMES = frozenset({"-", "na", "n/a", "not available", "unnamed", "unknown"})
MAX_PDF_PAGES = 200
MAX_EXTRACTED_TEXT_BYTES = 2 * 1024 * 1024


class MultiMfScopeIntegrityError(ValueError):
    """The installed parser collapsed or could not reconcile MF folio scopes."""


@dataclass(frozen=True)
class NsdlParserProvenance:
    casparser_result_type: Optional[str]
    library_rejection_class: Optional[str]
    bundled_isin_sqlite_present: bool
    adapter_path: str


@dataclass(frozen=True)
class NsdlParseResult:
    snapshot: NsdlSnapshotV1
    provenance: NsdlParserProvenance
    # Never place these names on the snapshot wire or in parser logging.  They
    # exist only until an authenticated confirmation creates owner-scoped facts.
    account_source_names: tuple[tuple[str, str], ...]


class NsdlSnapshotParser:
    """Adapt casparser's typed NSDL model before considering a narrow fallback."""

    def can_parse(self, attachment: Any, target_pan: Optional[str] = None) -> bool:
        filename = (getattr(attachment, "filename", "") or "").lower()
        payload = getattr(attachment, "payload_bytes", b"") or b""
        return "nsdl" in filename or "ecas" in filename or "e-cas" in filename or b"NSDL" in payload[:4096]

    def parse(
        self,
        stream: io.BytesIO,
        entity_profile: Optional[Any] = None,
        password: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> NsdlSnapshotV1:
        expected_pan = getattr(entity_profile, "pan", None) if entity_profile else None
        return self.parse_pdf_bytes(
            stream.getvalue(),
            password=password or "",
            expected_pan=expected_pan,
            portfolio_id="layout-gate-transient",
            hmac_secret=b"layout-gate-transient-secret",
        ).snapshot

    def parse_pdf_bytes(
        self,
        pdf_bytes: bytes,
        *,
        password: str,
        expected_pan: Optional[str],
        portfolio_id: str,
        hmac_secret: bytes,
        require_owner_pan: bool = True,
    ) -> NsdlParseResult:
        if not pdf_bytes.startswith(b"%PDF"):
            raise NsdlSnapshotError("ERR_NSDL_UNSUPPORTED_LAYOUT")
        if not portfolio_id or not hmac_secret:
            raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
        try:
            with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as document:
                pass
        except pikepdf.PasswordError:
            raise NsdlSnapshotError("ERR_NSDL_PASSWORD_INVALID") from None
        except pikepdf.PdfError:
            raise NsdlSnapshotError("ERR_NSDL_UNSUPPORTED_LAYOUT") from None

        self._validate_pdfium_text_limits(pdf_bytes, password)

        typed_data, typed_type, library_rejection = self._read_typed_nsdl(pdf_bytes, password)
        bundled_sqlite = (Path(casparser_isin.__file__).resolve().parent / "isin.db").is_file()
        if not bundled_sqlite:
            raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")

        if typed_data is None or not typed_data.accounts:
            raise NsdlSnapshotError("ERR_NSDL_UNSUPPORTED_LAYOUT")
        snapshot = self._adapt_typed_data(
            typed_data,
            expected_pan,
            portfolio_id,
            hmac_secret,
            require_owner_pan=require_owner_pan,
        )
        return NsdlParseResult(
            snapshot,
            NsdlParserProvenance(typed_type, library_rejection, True, "casparser-typed"),
            self._typed_account_source_names(typed_data, snapshot),
        )

    @staticmethod
    def _validate_pdfium_text_limits(pdf_bytes: bytes, password: str) -> None:
        """Count transient, actual PDFium UTF-8 text before casparser receives a file."""
        document = None
        try:
            document = pypdfium2.PdfDocument(pdf_bytes, password=password)
            if len(document) > MAX_PDF_PAGES:
                raise NsdlSnapshotError("ERR_NSDL_LIMIT_EXCEEDED")
            extracted_size = 0
            for index in range(len(document)):
                page = document[index]
                text_page = page.get_textpage()
                try:
                    extracted_size += len(text_page.get_text_range().encode("utf-8"))
                finally:
                    text_page.close()
                    page.close()
                if extracted_size > MAX_EXTRACTED_TEXT_BYTES:
                    raise NsdlSnapshotError("ERR_NSDL_LIMIT_EXCEEDED")
        except NsdlSnapshotError:
            raise
        except Exception as error:
            raise NsdlSnapshotError("ERR_NSDL_UNSUPPORTED_LAYOUT") from error
        finally:
            if document is not None:
                document.close()

    @staticmethod
    def _read_typed_nsdl(pdf_bytes: bytes, password: str) -> tuple[Optional[NSDLCASData], Optional[str], Optional[str]]:
        path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(prefix="nsdl-", suffix=".pdf", delete=False) as temporary:
                temporary.write(pdf_bytes)
                path = temporary.name
            data = casparser.read_cas_pdf(path, password=password, output="dict")
            if isinstance(data, NSDLCASData):
                return NsdlSnapshotParser._restore_mf_folio_scopes(path, password, data), type(data).__name__, None
            return None, type(data).__name__ if data is not None else None, "UnexpectedResultType"
        except Exception as error:
            # Never retain or emit source text. The category documents why the
            # synthetic-only fallback was selected without becoming a parser log.
            return None, None, type(error).__name__
        finally:
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _restore_mf_folio_scopes(path: str, password: str, data: NSDLCASData) -> NSDLCASData:
        """Restore separate MF-folio accounts when casparser merges their sections.

        casparser 1.4.0 uses a singleton account for all ``Mutual Fund Folios
        (F)`` sections. This adapter-only repair rebuilds those source scopes
        from the installed parser's in-memory blocks and fails closed on any
        scope or total mismatch. It never emits source text or values.
        """
        atoms = casparser_pageobj.extract_atoms(path, password)
        blocks = casparser_pageobj.blocks_from_atoms(atoms)
        pending_owners: list[DematOwner] = []
        source_roster: list[DematAccount] = []
        source_accounts: list[DematAccount] = []
        for block in blocks:
            if block.page != 2:
                continue
            text = block.text()
            lowered = text.casefold()
            if "in the single name of" in lowered or "in the joint names of" in lowered or "in the joint name of" in lowered:
                pending_owners = []
                continue
            if casparser_nsdl.PAN_RE.search(text):
                pending_owners.extend(
                    DematOwner(name=match.group(1).strip(), PAN=match.group(2).strip())
                    for match in casparser_nsdl.PAN_RE.finditer(text)
                )
                continue
            if casparser_nsdl._is_summary_mf_folios_row(block):
                account = casparser_nsdl._mf_folios_account_from_summary(block, list(pending_owners))
                source_roster.append(account)
                source_accounts.append(account)
                continue
            if casparser_nsdl._is_summary_demat_row(block):
                account, _ = casparser_nsdl._account_from_summary_row(block, list(pending_owners))
                source_roster.append(account)

        if len(source_accounts) <= 1:
            return NsdlSnapshotParser._repair_missing_bond_names(data, blocks)

        groups: list[list[MutualFund]] = []
        active_group: Optional[list[MutualFund]] = None
        # The installed parser has already collected warnings for these rows.
        # Replaying them into that list would double-count every warning.
        replay_warnings: list[str] = []
        benign_zero_warnings: Counter[str] = Counter()
        for block in blocks:
            if block.page <= 2:
                continue
            if block.text().strip().casefold() == "mutual fund folios (f)":
                if active_group is not None and active_group:
                    groups.append(active_group)
                active_group = []
                continue
            if active_group is None:
                continue
            warning_start = len(replay_warnings)
            parsed = casparser_nsdl._parse_mf_holdings_row(block, replay_warnings)
            if parsed is not None:
                active_group.append(parsed)
                new_warnings = replay_warnings[warning_start:]
                if NsdlSnapshotParser._source_zero_mf_warning(block, parsed, new_warnings):
                    benign_zero_warnings.update(new_warnings)
        if active_group:
            groups.append(active_group)

        original_counts = Counter(data.parse_warnings)
        if any(count > original_counts[warning] for warning, count in Counter(replay_warnings).items()):
            raise MultiMfScopeIntegrityError("MF folio warning replay does not match typed source")
        removable = benign_zero_warnings.copy()
        retained_warnings = []
        for warning in data.parse_warnings:
            if removable[warning]:
                removable[warning] -= 1
            else:
                retained_warnings.append(warning)
        repaired = NsdlSnapshotParser._replace_mf_folio_accounts(
            data, source_roster, source_accounts, groups, retained_warnings
        )
        return NsdlSnapshotParser._repair_missing_bond_names(repaired, blocks)

    @staticmethod
    def _source_zero_mf_warning(block: Any, row: MutualFund, warnings: list[str]) -> bool:
        """Ignore tail inference only when every printed amount after the folio is zero."""
        if warnings != [f"MF holdings {row.isin}: no closing nav/value pair; inferred from max tail"]:
            return False
        if row.balance != 0 or row.nav != 0 or row.value != 0:
            return False
        isin_index = casparser_nsdl._isin_cell_index(block)
        if isin_index is None:
            return False
        after_isin = block.cells[isin_index + 1:]
        folio_index = next((index for index, cell in enumerate(after_isin) if casparser_nsdl._looks_numeric(cell.text)), None)
        if folio_index is None:
            return False
        folio = after_isin[folio_index]
        amounts = after_isin[folio_index + 1:]
        return (
            len(amounts) >= 3
            and casparser_nsdl._is_folio_token(folio.text)
            and all(casparser_nsdl._looks_numeric(cell.text) and casparser_nsdl._to_decimal(cell.text) == 0 for cell in amounts)
        )

    @staticmethod
    def _repair_missing_bond_names(data: NSDLCASData, blocks: list[Any]) -> NSDLCASData:
        """Recover a bond name from its uniquely matching printed row."""
        repaired_accounts = []
        for account in data.accounts:
            bonds = []
            for bond in account.bonds:
                if bond.name or not bond.isin:
                    bonds.append(bond)
                    continue
                candidates = []
                for block in blocks:
                    if block.page <= 2 or len(block.cells) < 3:
                        continue
                    if block.cells[0].text.split("\n", 1)[0].strip() != bond.isin:
                        continue
                    source_name = block.cells[1].text.replace("\n", " ").strip()
                    if not source_name or source_name.casefold() in _PLACEHOLDER_NAMES or casparser_nsdl._looks_numeric(source_name):
                        continue
                    source_bond = casparser_nsdl._parse_bond_summary_row(block)
                    if source_bond is None or source_bond.model_dump(mode="json", exclude={"name"}) != bond.model_dump(mode="json", exclude={"name"}):
                        continue
                    candidates.append(source_name)
                bonds.append(bond.model_copy(update={"name": candidates[0]}) if len(candidates) == 1 else bond)
            repaired_accounts.append(account.model_copy(update={"bonds": bonds}))
        return data.model_copy(update={"accounts": repaired_accounts})

    @staticmethod
    def _replace_mf_folio_accounts(
        data: NSDLCASData,
        source_roster: list[DematAccount],
        source_accounts: list[DematAccount],
        groups: list[list[MutualFund]],
        warnings: Optional[list[str]] = None,
    ) -> NSDLCASData:
        """Apply prevalidated source MF scopes without accepting a merged account."""
        if len(groups) != len(source_accounts):
            raise MultiMfScopeIntegrityError("MF folio source scope count does not match detailed section count")
        typed_mf_accounts = [account for account in data.accounts if account.type == "Mutual Fund Folios"]
        # casparser 1.4.0 keeps only the first MF summary row's balance on its
        # singleton account, even while appending holdings from all MF sections.
        # Reconcile full rows here; each repaired scope is checked against its
        # own source summary balance below.
        # casparser enriches typed rows with AMFI code and scheme type after
        # reading the PDF. The replayed source rows lack those two DB fields.
        # Compare every printed/parser field, then carry the matching typed
        # enrichment onto each restored source scope.
        def row_key(row: MutualFund) -> str:
            return json.dumps(row.model_dump(mode="json", exclude={"amfi", "type"}), sort_keys=True, separators=(",", ":"))
        typed_rows = [row for account in typed_mf_accounts for row in account.mutual_funds]
        if Counter(map(row_key, typed_rows)) != Counter(row_key(row) for group in groups for row in group):
            raise MultiMfScopeIntegrityError("MF folio reconstructed holdings do not match typed source")
        enriched_by_source: dict[str, list[MutualFund]] = defaultdict(list)
        for row in typed_rows:
            enriched_by_source[row_key(row)].append(row)
        repaired_accounts: list[DematAccount] = []
        for account, mutual_funds in zip(source_accounts, groups):
            if not mutual_funds or sum((row.value for row in mutual_funds), Decimal(0)) != account.balance:
                raise MultiMfScopeIntegrityError("MF folio source total does not match detailed section total")
            enriched_rows = []
            for row in mutual_funds:
                typed_row = enriched_by_source[row_key(row)].pop()
                enriched_rows.append(row.model_copy(update={"amfi": typed_row.amfi, "type": typed_row.type}))
            repaired_accounts.append(account.model_copy(update={"mutual_funds": enriched_rows}))

        non_mf_by_source_key = {
            (account.type, account.dp_id, account.client_id): account
            for account in data.accounts
            if account.type != "Mutual Fund Folios"
        }
        if len(non_mf_by_source_key) != sum(account.type != "Mutual Fund Folios" for account in data.accounts):
            raise MultiMfScopeIntegrityError("duplicate non-MF source account key")
        repaired_iterator = iter(repaired_accounts)
        ordered_accounts: list[DematAccount] = []
        for source_account in source_roster:
            source_key = (source_account.type, source_account.dp_id, source_account.client_id)
            if source_account.type == "Mutual Fund Folios":
                replacement = next(repaired_iterator, None)
            else:
                replacement = non_mf_by_source_key.pop(source_key, None)
            if replacement is None:
                raise MultiMfScopeIntegrityError("source roster account does not match typed account")
            ordered_accounts.append(replacement)
        if non_mf_by_source_key or next(repaired_iterator, None) is not None:
            raise MultiMfScopeIntegrityError("typed account is absent from source roster")
        return data.model_copy(update={
            "accounts": ordered_accounts,
            "parse_warnings": list(data.parse_warnings) if warnings is None else warnings,
        })

    def _adapt_typed_data(
        self,
        data: NSDLCASData,
        expected_pan: Optional[str],
        portfolio_id: str,
        secret: bytes,
        *,
        require_owner_pan: bool = True,
    ) -> NsdlSnapshotV1:
        if require_owner_pan:
            normalized_expected_pan = self._normalize_pan(expected_pan)
            for account in data.accounts:
                account_pans = {self._normalize_pan(owner.PAN) for owner in account.owners if owner.PAN}
                if normalized_expected_pan not in account_pans:
                    raise NsdlSnapshotError("ERR_NSDL_OWNER_MISMATCH")
        as_of = self._typed_as_of_date(data)
        accounts: list[NsdlAccount] = []
        holdings: list[NsdlHolding] = []
        sections: list[str] = []
        missing_values = 0
        for account_index, account in enumerate(data.accounts):
            section = "MUTUAL_FUND" if account.type == "Mutual Fund Folios" else "DEMAT"
            sections.append(section)
            raw_scope = "|".join((account.type, account.dp_id or "", account.client_id or "", str(account_index)))
            scope_id = opaque_id(secret, portfolio_id, "account", raw_scope)
            accounts.append(NsdlAccount(scope_id, section, f"{section.replace('_', ' ').title()} account"))
            for kind, quantity, price, value, isin, name, instrument_type in self._typed_rows(account):
                if kind not in sections:
                    sections.append(kind)
                if quantity < 0 or (price is not None and price < 0) or (value is not None and value < 0):
                    raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
                statement_price = canonical_decimal(price) if price is not None and (price != 0 or quantity == 0) else None
                statement_value = canonical_decimal(value) if value is not None and (value != 0 or quantity == 0) else None
                if statement_value is None:
                    missing_values += 1
                if not name or name.strip().casefold() in _PLACEHOLDER_NAMES:
                    raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
                holdings.append(
                    NsdlHolding(
                        opaque_id(secret, portfolio_id, "holding", scope_id, isin or "", name or "", str(len(holdings))),
                        scope_id,
                        isin or None,
                        name,
                        instrument_type,
                        canonical_decimal(quantity),
                        "INR" if statement_value is not None else None,
                        statement_price,
                        statement_value,
                    )
                )
        unsupported = ["NPS"] if data.nps is not None else []
        warnings = tuple("casparser-warning" for _ in data.parse_warnings)
        return self._snapshot(
            portfolio_id, as_of, accounts, holdings, sections, unsupported, missing_values, warnings
        )

    @staticmethod
    def _typed_account_source_names(data: NSDLCASData, snapshot: NsdlSnapshotV1) -> tuple[tuple[str, str], ...]:
        if len(data.accounts) != len(snapshot.accounts):
            raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
        names: list[tuple[str, str]] = []
        for typed_account, snapshot_account in zip(data.accounts, snapshot.accounts):
            name = getattr(typed_account, "name", None)
            if not isinstance(name, str) or not name.strip() or name.strip().casefold() in _PLACEHOLDER_NAMES:
                raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
            names.append((snapshot_account.account_scope_id, name.strip()))
        return tuple(names)

    @staticmethod
    def _typed_rows(account: Any):
        for row in account.equities:
            yield "DEMAT", row.num_shares, row.price, row.value, row.isin, row.name, "EQUITY"
        for row in account.mutual_funds:
            yield "MUTUAL_FUND", row.balance, row.nav, row.value, row.isin, row.name, row.type or "MUTUAL_FUND"
        for row in account.bonds:
            yield "DEMAT", row.num_bonds, row.market_price, row.value, row.isin, row.name, "BOND"

    @staticmethod
    def _typed_as_of_date(data: NSDLCASData) -> date:
        for candidate in (getattr(data.statement_period, "to", None), getattr(data.statement_period, "from", None)):
            if candidate:
                for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
                    try:
                        return date.fromisoformat(candidate) if fmt == "%Y-%m-%d" else datetime.strptime(candidate, fmt).date()
                    except (TypeError, ValueError):
                        continue
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")

    @staticmethod
    def _normalize_pan(value: Optional[str]) -> str:
        normalized = re.sub(r"\s+", "", value or "").upper()
        if not _PAN_RE.fullmatch(normalized):
            raise NsdlSnapshotError("ERR_NSDL_OWNER_MISMATCH")
        return normalized

    @staticmethod
    def _snapshot(
        portfolio_id: str,
        as_of: date,
        accounts: list[NsdlAccount],
        holdings: list[NsdlHolding],
        sections: list[str],
        unsupported: list[str],
        missing_values: int,
        warnings: list[str] | tuple[str, ...],
    ) -> NsdlSnapshotV1:
        coverage = NsdlCoverage(
            complete=not unsupported and not missing_values and not warnings,
            sections=tuple(dict.fromkeys(sections)),
            unsupported_sections=tuple(dict.fromkeys(unsupported)),
            missing_values=missing_values,
            warnings=tuple(warnings),
        )
        return NsdlSnapshotV1(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            coverage=coverage,
            accounts=tuple(accounts),
            holdings=tuple(holdings),
            totals_by_currency=totals_from_holdings(holdings) if coverage.complete else (),
            parser_version=PARSER_VERSION,
        )
