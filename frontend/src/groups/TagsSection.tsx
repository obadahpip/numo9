"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { groupsApi, refusal, type Tag, type TagColour } from "./api";
import { m } from "./messages";
import { TagChip, TagPicker } from "./TagPicker";

/** The practice's tags (V-02-T10): list with usage counts, and the picker to create inline. */
export function TagsSection({ practice }: { practice: string }) {
  const t = useFormatMessage();
  const [tags, setTags] = useState<Tag[]>([]);
  const [announcement, setAnnouncement] = useState("");
  const colourLabels = useMemo<Record<TagColour, string>>(
    () => ({
      red: t(m.colourRed),
      orange: t(m.colourOrange),
      amber: t(m.colourAmber),
      olive: t(m.colourOlive),
      green: t(m.colourGreen),
      teal: t(m.colourTeal),
      cyan: t(m.colourCyan),
      blue: t(m.colourBlue),
      indigo: t(m.colourIndigo),
      violet: t(m.colourViolet),
      magenta: t(m.colourMagenta),
      slate: t(m.colourSlate),
    }),
    [t],
  );
  const load = useCallback(async () => {
    const result = await groupsApi.tags(practice);
    if (result.status === 200 && Array.isArray(result.body.tags)) setTags(result.body.tags);
  }, [practice]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section aria-labelledby="tags-heading" className="flex flex-col gap-3" data-tags-section="">
      <div>
        <h2 id="tags-heading" className="text-lg font-bold text-fg">
          {t(m.tagsTitle)}
        </h2>
        <p className="text-sm text-fg-muted">{t(m.tagsIntro)}</p>
      </div>
      {tags.length ? (
        <ul className="flex flex-wrap gap-2" data-tag-list="">
          {tags.map((tag) => (
            <li key={tag.id} className="flex items-center gap-1">
              <TagChip tag={tag} />
              <span className="text-xs text-fg-muted">
                {t(m.tagUsage, { count: tag.organisation_count })}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-fg-muted">{t(m.tagsEmpty)}</p>
      )}
      <div className="max-w-md">
        <TagPicker
          tags={tags}
          colourLabels={colourLabels}
          onSelect={(tag) => setAnnouncement(tag.name)}
          onCreate={async (name, colour) => {
            const result = await groupsApi.createTag(practice, name, colour);
            if (result.status !== 201) return refusal(result) ?? t(m.failed);
            setTags((current) =>
              [...current, result.body].sort((a, b) => a.name.localeCompare(b.name)),
            );
            setAnnouncement(t(m.tagCreated, { name: result.body.name }));
            return result.body;
          }}
        />
      </div>
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </section>
  );
}
