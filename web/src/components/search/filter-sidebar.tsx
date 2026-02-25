"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type { FacetCounts } from "@/types/search";

interface FilterSidebarProps {
  params: {
    regions: string[];
    portals: string[];
    closing_date_from: Date | null;
    closing_date_to: Date | null;
    posting_date_from: Date | null;
    posting_date_to: Date | null;
    value_min: number | null;
    value_max: number | null;
    classification_codes: string[];
    include_closed: boolean;
  };
  setFilter: (updates: Record<string, unknown>) => void;
  facets: FacetCounts | null;
}

/**
 * Always-visible filter sidebar (Amazon-style layout).
 * Contains: regions, portals, posting date, closing date, value range,
 * classification codes, and include_closed toggle.
 */
export function FilterSidebar({
  params,
  setFilter,
  facets,
}: FilterSidebarProps) {
  const [codeInput, setCodeInput] = useState("");

  const hasActiveFilters =
    params.regions.length > 0 ||
    params.portals.length > 0 ||
    params.closing_date_from !== null ||
    params.closing_date_to !== null ||
    params.posting_date_from !== null ||
    params.posting_date_to !== null ||
    params.value_min !== null ||
    params.value_max !== null ||
    params.classification_codes.length > 0 ||
    params.include_closed;

  function handleClearAll() {
    setFilter({
      regions: [],
      portals: [],
      closing_date_from: null,
      closing_date_to: null,
      posting_date_from: null,
      posting_date_to: null,
      value_min: null,
      value_max: null,
      classification_codes: [],
      include_closed: false,
    });
  }

  function toggleRegion(region: string) {
    const current = params.regions;
    const next = current.includes(region)
      ? current.filter((r) => r !== region)
      : [...current, region];
    setFilter({ regions: next });
  }

  function togglePortal(portal: string) {
    const current = params.portals;
    const next = current.includes(portal)
      ? current.filter((p) => p !== portal)
      : [...current, portal];
    setFilter({ portals: next });
  }

  function addClassificationCode() {
    const code = codeInput.trim().toUpperCase();
    if (code && !params.classification_codes.includes(code)) {
      setFilter({
        classification_codes: [...params.classification_codes, code],
      });
    }
    setCodeInput("");
  }

  function removeClassificationCode(code: string) {
    setFilter({
      classification_codes: params.classification_codes.filter(
        (c) => c !== code
      ),
    });
  }

  function formatDateForInput(date: Date | null): string {
    if (!date) return "";
    return date.toISOString().split("T")[0];
  }

  function parseDateInput(value: string): Date | null {
    if (!value) return null;
    const d = new Date(value + "T00:00:00");
    return isNaN(d.getTime()) ? null : d;
  }

  return (
    <aside className="w-64 shrink-0">
      <ScrollArea className="h-[calc(100vh-8rem)]">
        <div className="space-y-4 pr-3">
          {/* Header + Clear All */}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Filters</h2>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="xs"
                onClick={handleClearAll}
                className="text-muted-foreground"
              >
                Clear all
              </Button>
            )}
          </div>

          <Separator />

          {/* Include Closed Listings */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Checkbox
                id="include-closed"
                checked={params.include_closed}
                onCheckedChange={(checked) =>
                  setFilter({ include_closed: checked === true })
                }
              />
              <Label htmlFor="include-closed" className="text-sm cursor-pointer">
                Include closed listings
              </Label>
            </div>
          </div>

          <Separator />

          {/* Regions / Provinces */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Regions
            </h3>
            {facets && facets.provinces.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {facets.provinces.map((facet) => (
                  <div key={facet.value} className="flex items-center gap-2">
                    <Checkbox
                      id={`region-${facet.value}`}
                      checked={params.regions.includes(facet.value)}
                      onCheckedChange={() => toggleRegion(facet.value)}
                    />
                    <Label
                      htmlFor={`region-${facet.value}`}
                      className="text-sm cursor-pointer flex-1 truncate"
                    >
                      {facet.value}
                    </Label>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {facet.count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No regions available</p>
            )}
          </div>

          <Separator />

          {/* Source Portals */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Source Portals
            </h3>
            {facets && facets.portals.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {facets.portals.map((facet) => (
                  <div key={facet.value} className="flex items-center gap-2">
                    <Checkbox
                      id={`portal-${facet.value}`}
                      checked={params.portals.includes(facet.value)}
                      onCheckedChange={() => togglePortal(facet.value)}
                    />
                    <Label
                      htmlFor={`portal-${facet.value}`}
                      className="text-sm cursor-pointer flex-1 truncate"
                    >
                      {facet.value}
                    </Label>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {facet.count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No portals available</p>
            )}
          </div>

          <Separator />

          {/* Posting Date Range */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Posting Date
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs text-muted-foreground">From</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={formatDateForInput(params.posting_date_from)}
                  onChange={(e) =>
                    setFilter({ posting_date_from: parseDateInput(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">To</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={formatDateForInput(params.posting_date_to)}
                  onChange={(e) =>
                    setFilter({ posting_date_to: parseDateInput(e.target.value) })
                  }
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Closing Date Range */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Closing Date
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs text-muted-foreground">From</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={formatDateForInput(params.closing_date_from)}
                  onChange={(e) =>
                    setFilter({ closing_date_from: parseDateInput(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">To</Label>
                <Input
                  type="date"
                  className="h-8 text-xs"
                  value={formatDateForInput(params.closing_date_to)}
                  onChange={(e) =>
                    setFilter({ closing_date_to: parseDateInput(e.target.value) })
                  }
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Contract Value Range */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Contract Value
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs text-muted-foreground">Min ($)</Label>
                <Input
                  type="number"
                  placeholder="0"
                  className="h-8 text-xs"
                  value={params.value_min ?? ""}
                  onChange={(e) =>
                    setFilter({
                      value_min: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Max ($)</Label>
                <Input
                  type="number"
                  placeholder="Any"
                  className="h-8 text-xs"
                  value={params.value_max ?? ""}
                  onChange={(e) =>
                    setFilter({
                      value_max: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Classification Codes */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
              Classification Codes
            </h3>
            <div className="flex gap-1">
              <Input
                type="text"
                placeholder="e.g. N7030"
                className="h-8 text-xs flex-1"
                value={codeInput}
                onChange={(e) => setCodeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addClassificationCode();
                  }
                }}
              />
              <Button
                variant="outline"
                size="xs"
                onClick={addClassificationCode}
                className="h-8"
              >
                Add
              </Button>
            </div>
            {params.classification_codes.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {params.classification_codes.map((code) => (
                  <Badge
                    key={code}
                    variant="secondary"
                    className="text-xs gap-1 cursor-pointer"
                    onClick={() => removeClassificationCode(code)}
                  >
                    {code}
                    <X className="h-3 w-3" />
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      </ScrollArea>
    </aside>
  );
}
