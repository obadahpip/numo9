"use client";

/**
 * A staff member's page (V-05): who they are (from the staff list) and their assignments
 * (V-05-T04); the activity heatmap joins with V-05-T08.
 */
import { ErrorState } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { staffApi, type StaffMember } from "./api";
import { AssignmentEditor } from "./AssignmentEditor";
import { m } from "./messages";

export function StaffMemberScreen({ practice, member }: { practice: string; member: string }) {
  const fm = useFormatMessage();
  const [person, setPerson] = useState<StaffMember | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void staffApi.list(practice).then((result) => {
      if (cancelled) return;
      const found = result.status === 200 ? result.body.staff.find((s) => s.id === member) : null;
      if (found) setPerson(found);
      else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [practice, member, attempt]);

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
        headingLevel={2}
      />
    );
  }
  if (!person) return null;
  return (
    <div className="flex flex-col gap-6" data-staff-member={person.id}>
      <div>
        <h1 className="text-2xl font-bold text-fg">{person.name || person.email}</h1>
        <p className="text-sm text-fg-muted">
          {fm(m.personLine, { role: person.role_label, email: person.email })}
        </p>
      </div>
      <AssignmentEditor
        practice={practice}
        user={{ id: person.id, name: person.name || person.email }}
      />
    </div>
  );
}
