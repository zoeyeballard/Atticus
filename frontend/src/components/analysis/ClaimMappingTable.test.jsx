import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ClaimMappingTable from "./ClaimMappingTable.jsx";

const mappings = [
  { limitation_text: "a priority queue", mapped_to_reference: "US11,345,678", reference_passage: "Fig. 3" },
];

describe("ClaimMappingTable", () => {
  it("renders a row per mapping", () => {
    render(<ClaimMappingTable mappings={mappings} />);
    expect(screen.getByText("a priority queue")).toBeInTheDocument();
    expect(screen.getByText(/US11,345,678/)).toBeInTheDocument();
  });

  it("fires the source-viewer callback when [View ↗] is clicked", () => {
    const onView = vi.fn();
    render(<ClaimMappingTable mappings={mappings} onViewSource={onView} />);
    fireEvent.click(screen.getByText(/View/));
    expect(onView).toHaveBeenCalledWith("US11,345,678");
  });

  it("shows a friendly message when there are no mappings", () => {
    render(<ClaimMappingTable mappings={[]} />);
    expect(screen.getByText(/No limitation mappings/i)).toBeInTheDocument();
  });
});
