# Workspace access and SSO

## Invitations and roles
An invitation expires after 72 hours. A workspace owner or administrator can send a new invitation from Settings, then Members. If a user receives an expired invitation message, ask an administrator to resend it. Sending a new invitation does not change the user's assigned role.

## Single sign-on
SAML single sign-on is available on the fictional Enterprise plan. The workspace owner configures the identity provider metadata and verifies the callback URL. A user's email address must match the identity provider's NameID. Support should check the error code and metadata configuration before escalating a login failure.

## Locked-out administrators
If every administrator is locked out after an SSO change, prepare an urgent access escalation and collect the workspace ID and the identity provider's error message. Support must not disable SSO, change roles, or bypass identity verification. A designated access team reviews account recovery requests.
