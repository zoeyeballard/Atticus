import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import VerificationBadge from "./VerificationBadge.jsx";

describe("VerificationBadge", () => {
  it("renders Verified for verified status", () => {
    render(<VerificationBadge status="verified" />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("renders Review Suggested for partial status", () => {
    render(<VerificationBadge status="partial" />);
    expect(screen.getByText("Review Suggested")).toBeInTheDocument();
  });

  it("renders Unverified for fabricated status", () => {
    render(<VerificationBadge status="fabricated" />);
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("renders N/A for unverifiable status", () => {
    render(<VerificationBadge status="unverifiable" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("derives state from a numeric confidence", () => {
    render(<VerificationBadge confidence={0.9} />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("exposes an explanatory tooltip (no ML jargon)", () => {
    render(<VerificationBadge status="verified" />);
    const el = screen.getByText("Verified");
    expect(el.getAttribute("title")).toMatch(/confirmed against the original source/i);
  });
});
