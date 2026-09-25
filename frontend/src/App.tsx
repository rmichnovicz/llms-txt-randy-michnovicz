import { useEffect, useRef, useState } from "react";
import Start from "./Start";
import Workspace from "./Workspace";

const currentRoute = () => window.location.pathname + window.location.search;

export default function App() {
  const [route, setRoute] = useState(currentRoute);
  const currentUrl = useRef(route);
  const canLeave = useRef(() => true);
  useEffect(() => {
    const update = () => {
      if (canLeave.current()) {
        currentUrl.current = currentRoute();
        setRoute(currentUrl.current);
      } else history.pushState(null, "", currentUrl.current);
    };
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  function navigate(url: string) {
    if (!canLeave.current()) return;
    history.pushState(null, "", url);
    currentUrl.current = url;
    setRoute(url);
  }
  function canonicalize(url: string) {
    history.replaceState(null, "", url);
    currentUrl.current = url;
  }
  const url = new URL(route, window.location.origin);
  const siteId = url.pathname.match(/^\/s\/([a-f0-9-]+)$/)?.[1];
  return siteId ? (
    <Workspace
      key={route}
      siteId={siteId}
      doc={url.searchParams.get("doc")}
      navigate={navigate}
      canonicalize={canonicalize}
      canLeave={canLeave}
    />
  ) : (
    <Start />
  );
}
