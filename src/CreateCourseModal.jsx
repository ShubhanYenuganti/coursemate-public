import { useState, forwardRef, useImperativeHandle } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";

function NotebookIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 6h4" />
      <path d="M2 10h4" />
      <path d="M2 14h4" />
      <path d="M2 18h4" />
      <rect x="6" y="3" width="16" height="18" rx="2" />
      <line x1="12" y1="9" x2="16" y2="9" />
      <line x1="12" y1="13" x2="16" y2="13" />
    </svg>
  );
}

const CreateCourseModal = forwardRef(function CreateCourseModal(_, ref) {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  useImperativeHandle(ref, () => ({
    open: () => {
      setTitle("");
      setDescription("");
      setError(null);
      setShowModal(true);
    },
  }));

  const openModal = () => {
    setTitle("");
    setDescription("");
    setError(null);
    setShowModal(true);
  };

  const handleOpenChange = (open) => {
    if (!open && creating) return;
    setShowModal(open);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setCreating(true);
    setError(null);

    try {
      const res = await fetch("/api/course", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ title: title.trim(), description: description.trim() || undefined }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setShowModal(false);
      navigate(`/course/${data.course.id}`, { state: { course: data.course } });
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={openModal}
        className="text-muted-foreground hover:text-foreground"
        title="New course"
        aria-label="New course"
      >
        <NotebookIcon />
      </Button>

      <Dialog open={showModal} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Course</DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="course-title">
                Title <span className="text-destructive">*</span>
              </Label>
              <Input
                id="course-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Introduction to Machine Learning"
                autoFocus
                disabled={creating}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="course-desc">
                Description <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Textarea
                id="course-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What is this course about?"
                rows={3}
                className="resize-none"
                disabled={creating}
              />
            </div>

            {error && (
              <p className="text-destructive text-sm">{error}</p>
            )}

            <DialogFooter className="pt-2">
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="outline"
                  disabled={creating}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </DialogClose>
              <Button
                type="submit"
                disabled={creating || !title.trim()}
                className="flex-1"
              >
                {creating ? (
                  <>
                    <div className="w-4 h-4 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
                    Creating…
                  </>
                ) : (
                  "Create Course"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
});

export default CreateCourseModal;
