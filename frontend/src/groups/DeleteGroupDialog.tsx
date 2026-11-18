"use client";

import { Button, Dialog } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { groupsApi, refusal, type Group, type GroupImpact } from "./api";
import { m } from "./messages";

/**
 * Delete-group dialog (V-02-T11): before deleting, it asks the API what the deletion affects
 * (`GET …/groups/<id>/impact`) and shows those counts — sub-groups, organisations (they stay
 * clients), staff assignments and the staff who would lose access to at least one client. The
 * delete button stays disabled until the counts are in.
 */
export function DeleteGroupDialog({
  group,
  onClose,
  onDeleted,
}: {
  group: Group;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const t = useFormatMessage();
  const [impact, setImpact] = useState<GroupImpact | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void groupsApi.impact(group.id).then((result) => {
      if (cancelled) return;
      if (result.status === 200) setImpact(result.body);
      else setError(refusal(result) ?? t(m.failed));
    });
    return () => {
      cancelled = true;
    };
  }, [group.id, t]);
  const remove = async () => {
    setBusy(true);
    const result = await groupsApi.remove(group.id);
    setBusy(false);
    if (result.status === 204) onDeleted();
    else setError(refusal(result) ?? t(m.failed));
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t(m.deleteTitle, { name: group.name })}
      closeLabel={t(m.close)}
      footer={
        <>
          <Button onClick={onClose}>{t(m.cancel)}</Button>
          <Button variant="danger" loading={busy} disabled={!impact} onClick={() => void remove()}>
            {t(m.deleteConfirm)}
          </Button>
        </>
      }
    >
      {impact ? (
        <div className="flex flex-col gap-2 text-sm text-fg" data-delete-impact="">
          <ul className="list-disc ps-5">
            <li data-impact="groups">{t(m.impactGroups, { count: impact.groups - 1 })}</li>
            <li data-impact="organisations">
              {t(m.impactOrganisations, { count: impact.organisations })}
            </li>
            <li data-impact="staff">
              {t(m.impactStaff, { count: impact.staff, assignments: impact.staff_assignments })}
            </li>
          </ul>
          <p className="font-semibold" data-impact="losing">
            {t(m.impactLosing, { count: impact.staff_losing_access })}
          </p>
        </div>
      ) : error ? null : (
        <p className="text-sm text-fg-muted">{t(m.impactLoading)}</p>
      )}
      {error ? (
        <p role="alert" className="mt-2 text-sm font-medium text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
