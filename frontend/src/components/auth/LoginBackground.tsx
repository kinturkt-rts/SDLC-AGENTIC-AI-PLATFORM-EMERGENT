/** CSS-only futuristic backdrop for the login screen. */
export function LoginBackground() {
  return (
    <div className="login-backdrop" aria-hidden>
      <div className="login-backdrop__gradient" />
      <div className="login-backdrop__grid" />
      <div className="login-backdrop__mesh" />
      <div className="login-backdrop__orb login-backdrop__orb--cyan" />
      <div className="login-backdrop__orb login-backdrop__orb--violet" />
      <div className="login-backdrop__orb login-backdrop__orb--blue" />
      <div className="login-backdrop__nodes">
        <span className="login-backdrop__node login-backdrop__node--1" />
        <span className="login-backdrop__node login-backdrop__node--2" />
        <span className="login-backdrop__node login-backdrop__node--3" />
        <span className="login-backdrop__node login-backdrop__node--4" />
        <span className="login-backdrop__node login-backdrop__node--5" />
        <span className="login-backdrop__line login-backdrop__line--1" />
        <span className="login-backdrop__line login-backdrop__line--2" />
        <span className="login-backdrop__line login-backdrop__line--3" />
      </div>
      <div className="login-backdrop__scan" />
    </div>
  );
}
