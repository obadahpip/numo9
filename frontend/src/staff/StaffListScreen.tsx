"use client";

/**
 * Practice staff list (V-05-T09, wireframe 33): name, practice role, organisations they can open,
 * last active and status (active, dormant, suspended, pending invitation), with the dormant-staff
 * widget above. Opening a row goes to the person's page (activity, assignments, suspend, remove);
 * a pending invitation has no page yet: it can be resent or withdrawn in place. "Invite staff"
 * sends a practice invitation with a role, valid 14 days (V-05-T03).
 */
import {
  DataGrid,
  EmptyState,
  ErrorState,
  formatDate,
  type AppLocale,
  type DataGridColumn,
  type DataGridLabels,
  type DataGridStatus,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { practiceStaffMemberUrl } from "@/routing/routes";

import { staffApi, type StaffMember } from "./api";
import { DormantStaffWidget } from "./DormantStaffWidget";
import {
  InviteStaffDialog,
  PendingInvitationActions,
  practiceRoleLabel,
} from "./InviteStaffDialog";
import type { StaffInvitation } from "./invitations";
import { im } from "./inviteMessages";
import { m } from "./messages";
import { StaffStatusBadge } from "./StaffStatusBadge";
import { staffStatus, staffStatusLabel, type StaffStatus } from "./status";

function useGridLabels(): DataGridLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(m.grid),
    search: fm(m.gridSearch),
    columns: fm(m.gridColumns),
    density: fm(m.gridDensity),
    comfortable: fm(m.gridComfortable),
    compact: fm(m.gridCompact),
    filterAll: fm(m.gridAll),
    filterChip: (column, value) => fm(m.gridChip, { column, value }),
    clearFilters: fm(m.gridClear),
    selectAll: fm(m.gridSelectAll),
    selectRow: (row) => fm(m.gridSelectRow, { row }),
    selectedCount: (count) => fm(m.gridSelected, { count }),
    clearSelection: fm(m.gridClearSelection),
    resultCount: (shown, total) => fm(m.gridResults, { shown, total }),
    loading: fm(m.loading),
  };
}

const STATUSES: StaffStatus[] = ["active", "dormant", "suspended", "pending"];

export function StaffListScreen({ practice }: { practice: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const labels = useGridLabels();
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [status, setStatus] = useState<DataGridStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const [notice, setNotice] = useState("");

  const asRow = (invitation: StaffInvitation, roleLabel: string): StaffMember => ({
    id: invitation.id,
    name: "",
    email: invitation.email,
    role: invitation.role,
    role_label: roleLabel,
    status: "pending",
    invitation_expires_at: invitation.expires_at,
    organisation_count: 0,
    last_login: null,
    dormant: false,
  });

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    void staffApi.list(practice).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.staff)) {
        setStaff(result.body.staff);
        setStatus("ready");
      } else {
        setStatus("error");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [practice, attempt]);

  const columns = useMemo<DataGridColumn<StaffMember>[]>(() => {
    const name = (row: StaffMember) => row.name || row.email;
    return [
      {
        id: "name",
        header: fm(m.colName),
        accessor: name,
        sortable: true,
        hideable: false,
        cell: (row) =>
          row.status === "pending" ? (
            <span className="flex flex-col">
              <span className="font-semibold">{name(row)}</span>
              <span className="text-xs text-fg-muted">{row.email}</span>
            </span>
          ) : (
            <span className="flex flex-col">
              <a
                href={practiceStaffMemberUrl(practice, row.id)}
                className="font-semibold text-fg underline"
                onClick={(event) => event.stopPropagation()}
              >
                {name(row)}
              </a>
              <span className="text-xs text-fg-muted">{row.email}</span>
            </span>
          ),
      },
      { id: "role", header: fm(m.colRole), accessor: (row) => row.role_label, sortable: true },
      {
        id: "organisations",
        header: fm(m.colOrganisations),
        accessor: (row) => row.organisation_count,
        sortable: true,
        align: "end",
        searchable: false,
      },
      {
        id: "last_active",
        header: fm(m.colLastActive),
        accessor: (row) => row.last_login ?? "",
        sortable: true,
        searchable: false,
        cell: (row) =>
          row.last_login ? formatDate(new Date(row.last_login), { locale }) : fm(m.never),
      },
      {
        id: "status",
        header: fm(m.colStatus),
        accessor: (row) => staffStatus(row),
        sortable: true,
        searchable: false,
        filterOptions: STATUSES.map((value) => ({ value, label: staffStatusLabel(value, fm) })),
        cell: (row) => {
          const value = staffStatus(row);
          return (
            <span className="flex flex-col items-start gap-1">
              <StaffStatusBadge status={value} />
              {row.status === "pending" && row.invitation_expires_at ? (
                <span className="text-xs text-fg-muted">
                  {fm(m.expires, {
                    date: formatDate(new Date(row.invitation_expires_at), { locale }),
                  })}
                </span>
              ) : null}
              {row.status === "pending" ? (
                <PendingInvitationActions
                  row={row}
                  onResent={(invitation) => {
                    setStaff((rows) =>
                      rows.map((r) =>
                        r.id === row.id
                          ? { ...r, invitation_expires_at: invitation.expires_at }
                          : r,
                      ),
                    );
                    setNotice(fm(im.resent, { email: row.email }));
                  }}
                  onRevoked={() => {
                    setStaff((rows) => rows.filter((r) => r.id !== row.id));
                    setNotice(fm(im.revoked, { email: row.email }));
                  }}
                  onError={setNotice}
                />
              ) : null}
            </span>
          );
        },
      },
    ];
  }, [fm, locale, practice]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg">{fm(m.listTitle)}</h1>
          <p className="text-sm text-fg-muted">{fm(m.listIntro)}</p>
        </div>
        <InviteStaffDialog
          practice={practice}
          onInvited={(invitation) => {
            setStaff((rows) => [
              ...rows,
              asRow(invitation, practiceRoleLabel(invitation.role, fm)),
            ]);
            setNotice(fm(im.sent, { email: invitation.email }));
          }}
        />
      </div>
      <p role="status" className="text-sm text-fg">
        {notice}
      </p>
      <DormantStaffWidget practice={practice} />
      <DataGrid
        data={staff}
        columns={columns}
        getRowId={(row) => row.id}
        getRowLabel={(row) => row.name || row.email}
        labels={labels}
        status={status}
        onRowOpen={(row) => {
          if (row.status !== "pending") {
            window.location.assign(practiceStaffMemberUrl(practice, row.id));
          }
        }}
        emptyState={<EmptyState title={fm(m.empty)} body={fm(m.emptyBody)} />}
        noResultsState={<EmptyState title={fm(m.noResults)} compact />}
        errorState={
          <ErrorState
            title={fm(m.listFailed)}
            retryLabel={fm(m.retry)}
            onRetry={() => setAttempt((n) => n + 1)}
            headingLevel={2}
          />
        }
      />
    </div>
  );
}
