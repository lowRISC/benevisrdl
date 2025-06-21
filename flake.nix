{
  description = "Python env for rdl2ot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
    lowrisc-nix.url = "github:lowRISC/lowrisc-nix";
  };

  outputs = {
    self,
    nixpkgs,
    uv2nix,
    pyproject-nix,
    pyproject-build-systems,
    lowrisc-nix,
  }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {
      inherit system;
    };
    peakrdl = lowrisc-nix.packages.${system}.peakrdl;

    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};
    overlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    pythonSet =
      (pkgs.callPackage pyproject-nix.build.packages {
        python = pkgs.python310;
      })
      .overrideScope
      (
        pkgs.lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
          (lowrisc-nix.lib.pyprojectOverrides {inherit pkgs;})
        ]
      );

      env = pythonSet.mkVirtualEnv "python-env" workspace.deps.default;
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      packages = [env];
      buildInputs = [peakrdl];
    };
    formatter.x86_64-linux = nixpkgs.legacyPackages.x86_64-linux.alejandra;
  };
}
