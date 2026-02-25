"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ExternalLink,
  Mail,
  Phone,
  FileText,
  Calendar,
  MapPin,
  DollarSign,
} from "lucide-react";
import { formatDate, formatCurrency } from "@/lib/format";
import type { ListingDetail } from "@/types/listing";

interface ListingDetailSheetProps {
  listing: ListingDetail | null;
  open: boolean;
  onClose: () => void;
  loading: boolean;
}

/** Color-coded status badge */
function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  let variant: "default" | "secondary" | "destructive" | "outline" = "default";
  let className = "";

  switch (normalized) {
    case "open":
    case "active":
      className = "bg-emerald-600 text-white hover:bg-emerald-700";
      break;
    case "closed":
      variant = "secondary";
      break;
    case "cancelled":
      variant = "destructive";
      break;
    case "awarded":
      className = "bg-blue-600 text-white hover:bg-blue-700";
      break;
    default:
      variant = "outline";
  }

  return (
    <Badge variant={variant} className={className}>
      {status}
    </Badge>
  );
}

/** Loading skeleton for the Sheet content */
function DetailSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-4 w-1/3" />
      </div>
      <Separator />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
      <Separator />
      <div className="space-y-2">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
      </div>
      <Separator />
      <div className="space-y-2">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-20 w-full" />
      </div>
      <Separator />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

/**
 * Slide-out Sheet panel showing full listing detail.
 *
 * LOCKED layout order:
 * a. Title
 * b. Status badge
 * c. Portal name
 * d. Dates (posting, closing, amended)
 * e. Metadata (province, value, classification codes)
 * f. Description
 * g. Documents
 * h. Contact card
 * i. Source link button
 */
export function ListingDetailSheet({
  listing,
  open,
  onClose,
  loading,
}: ListingDetailSheetProps) {
  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent
        side="right"
        className="sm:max-w-[600px] w-full p-0 flex flex-col"
      >
        {loading || !listing ? (
          <>
            <SheetHeader className="p-4">
              <SheetTitle>Loading listing...</SheetTitle>
              <SheetDescription>Fetching details</SheetDescription>
            </SheetHeader>
            <DetailSkeleton />
          </>
        ) : (
          <>
            {/* ===== HEADER ===== */}
            <SheetHeader className="px-6 pt-6 pb-0">
              {/* a. TITLE */}
              <SheetTitle className="text-lg leading-snug pr-8">
                {listing.title}
              </SheetTitle>

              {/* b. STATUS */}
              <div className="flex items-center gap-2 mt-1">
                <StatusBadge status={listing.status} />
              </div>

              {/* c. PORTAL NAME */}
              <SheetDescription className="mt-1">
                {listing.source_portal_name}
              </SheetDescription>
            </SheetHeader>

            {/* ===== SCROLLABLE BODY ===== */}
            <ScrollArea className="flex-1 overflow-y-auto">
              <div className="px-6 pb-6 space-y-5">

                {/* d. DATES */}
                <Separator />
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    Dates
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs">Posted</p>
                      <p className="font-medium">
                        {formatDate(listing.posting_date)}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Closes</p>
                      <p className="font-medium">
                        {formatDate(listing.closing_date)}
                      </p>
                    </div>
                    {listing.amended_date && (
                      <div className="col-span-2">
                        <p className="text-muted-foreground text-xs">Amended</p>
                        <p className="font-medium">
                          {formatDate(listing.amended_date)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* e. METADATA */}
                <Separator />
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">Province:</span>
                    <span className="font-medium">
                      {listing.province || "Not specified"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <DollarSign className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">Value:</span>
                    <span className="font-medium">
                      {formatCurrency(listing.value_min, listing.value_max)}
                    </span>
                  </div>
                  {listing.classification_codes.length > 0 && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1.5">
                        Classification Codes
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {listing.classification_codes.map((code) => (
                          <Badge key={code} variant="outline" className="text-xs">
                            {code}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* f. DESCRIPTION */}
                <Separator />
                <div>
                  <h4 className="text-sm font-medium mb-2">Description</h4>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                    {listing.description || "Not specified"}
                  </p>
                </div>

                {/* g. DOCUMENTS */}
                <Separator />
                <div>
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    Documents
                  </h4>
                  {listing.documents && listing.documents.length > 0 ? (
                    <div className="space-y-2">
                      {listing.documents.map((doc, idx) => (
                        <a
                          key={idx}
                          href={doc.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-3 rounded-md border p-3 text-sm hover:bg-muted/50 transition-colors"
                        >
                          <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">{doc.name}</p>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <Badge variant="outline" className="text-[10px] px-1.5">
                                {doc.type || "Document"}
                              </Badge>
                              {doc.date && (
                                <span>{formatDate(doc.date)}</span>
                              )}
                            </div>
                          </div>
                          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        </a>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No documents available
                    </p>
                  )}
                </div>

                {/* h. CONTACT CARD */}
                <Separator />
                <div>
                  <h4 className="text-sm font-medium mb-2">Contact Information</h4>
                  {listing.contact_info ? (
                    <div className="rounded-md border p-4 space-y-2">
                      {listing.contact_info.name && (
                        <p className="font-medium text-sm">
                          {listing.contact_info.name}
                        </p>
                      )}
                      {listing.contact_info.title && (
                        <p className="text-xs text-muted-foreground">
                          {listing.contact_info.title}
                        </p>
                      )}
                      {listing.contact_info.email && (
                        <a
                          href={`mailto:${listing.contact_info.email}`}
                          className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                        >
                          <Mail className="h-4 w-4" />
                          {listing.contact_info.email}
                        </a>
                      )}
                      {listing.contact_info.phone && (
                        <a
                          href={`tel:${listing.contact_info.phone}`}
                          className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                        >
                          <Phone className="h-4 w-4" />
                          {listing.contact_info.phone}
                        </a>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No contact information available
                    </p>
                  )}
                </div>

                {/* i. SOURCE LINK */}
                <Separator />
                <div>
                  {listing.source_url ? (
                    <Button size="lg" className="w-full" asChild>
                      <a
                        href={listing.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        View on {listing.source_portal_name}
                      </a>
                    </Button>
                  ) : (
                    <Button size="lg" className="w-full" disabled>
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Source URL not available
                    </Button>
                  )}
                </div>
              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
