/**
 * The standard shadcn/ui `cn()` helper — merges Tailwind classes,
 * resolving conflicts (e.g. `cn("p-2", condition && "p-4")` correctly
 * yields just "p-4" when true, not both). Every shadcn/ui component
 * generated via the CLI expects this to exist at this exact path.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
